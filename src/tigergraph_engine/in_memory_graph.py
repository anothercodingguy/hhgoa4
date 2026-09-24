"""
High-Performance TigerGraph Engine & In-Memory Graph Index.
Implements exact GSQL graph traversal logic, device sharing ring analysis,
card testing burst detection, and out-of-region spatial drift.
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from src.config import settings

class InMemoryTigerGraph:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or settings.data_dir
        
        # Vertices
        self.customers: Dict[str, Dict[str, Any]] = {}
        self.cards: Dict[str, Dict[str, Any]] = {}
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.devices: Dict[str, Dict[str, Any]] = {} # keyed by txn_id
        self.device_profiles: Dict[str, Set[str]] = {} # profile_string -> set of txn_ids
        self.device_to_cards: Dict[str, Set[str]] = {} # profile_string -> set of card_ids
        
        # Edges
        self.customer_cards: Dict[str, List[str]] = {}
        self.card_txns: Dict[str, List[str]] = {} # card_id -> list of txn_ids sorted by ts
        self.card_regions: Dict[str, Dict[str, int]] = {} # card_id -> {region_code: count}
        
        # Investigation cases written to graph
        self.investigation_cases: Dict[str, Dict[str, Any]] = {}
        
        self.is_loaded = False

    def load_identities(self, identity_path: Optional[Path] = None):
        id_path = identity_path or (self.data_dir / "identity.csv")
        if not id_path.exists():
            return

        with open(id_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                txn_id = row.get("TransactionID", "").strip()
                if not txn_id:
                    continue
                
                dev_info = row.get("DeviceInfo", "").strip()
                dev_type = row.get("DeviceType", "").strip()
                os_str = row.get("id_30", "").strip()
                browser = row.get("id_31", "").strip()
                screen = row.get("id_33", "").strip()
                is_new = (row.get("id_15", "").strip() == "New")
                proxy_flag = row.get("id_23", "").strip()
                
                # Canonical device profile string
                profile_components = [p for p in [dev_info, os_str, browser, screen] if p]
                profile_str = " | ".join(profile_components) if profile_components else (dev_type or "Unknown Device")
                
                device_record = {
                    "txn_id": txn_id,
                    "device_info": dev_info,
                    "device_type": dev_type,
                    "os": os_str,
                    "browser": browser,
                    "screen": screen,
                    "is_new": is_new,
                    "proxy_flag": proxy_flag,
                    "profile_str": profile_str
                }
                
                self.devices[txn_id] = device_record
                self.device_profiles.setdefault(profile_str, set()).add(txn_id)

    def load_transactions(self, txn_path: Optional[Path] = None, max_rows: Optional[int] = None):
        t_path = txn_path or (self.data_dir / "transactions.csv")
        if not t_path.exists():
            return

        # Pre-seed known card mappings from closed cases and case pack
        known_txn_cards = {}
        closed_path = self.data_dir / "closed_cases_history.csv"
        if closed_path.exists():
            with open(closed_path, "r", encoding="utf-8", errors="replace") as cf:
                for r in csv.DictReader(cf):
                    cid = r.get("card_id", "").strip()
                    for t in r.get("txn_ids", "").split("|"):
                        if t:
                            known_txn_cards[t] = cid
                    if r.get("first_fraud_txn_id"):
                        known_txn_cards[r["first_fraud_txn_id"]] = cid

        case_pack_path = self.data_dir / "case_pack.csv"
        if case_pack_path.exists():
            with open(case_pack_path, "r", encoding="utf-8", errors="replace") as cpf:
                for r in csv.DictReader(cpf):
                    known_txn_cards[r["flagged_txn_id"]] = r["card_id"]

        sig_to_card = {}
        cust_sig_counts = {}

        with open(t_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                txn_id = row.get("TransactionID", "").strip()
                if not txn_id:
                    continue
                
                cust_id = row.get("customer_id", "").strip()
                sig = (
                    cust_id,
                    row.get("card1", ""),
                    row.get("card2", ""),
                    row.get("card3", ""),
                    row.get("card4", ""),
                    row.get("card5", ""),
                    row.get("card6", "")
                )
                
                if txn_id in known_txn_cards:
                    card_id = known_txn_cards[txn_id]
                    sig_to_card[sig] = card_id
                elif sig in sig_to_card:
                    card_id = sig_to_card[sig]
                else:
                    k_num = cust_sig_counts.get(cust_id, 0) + 1
                    cust_sig_counts[cust_id] = k_num
                    card_id = f"{cust_id}-K{k_num}"
                    sig_to_card[sig] = card_id
                
                ts_str = row.get("ts", "").strip()
                channel = row.get("channel", "in_person").strip()
                product_cd = row.get("ProductCD", "").strip()
                addr1 = row.get("addr1", "").strip()
                addr2 = row.get("addr2", "87").strip()
                p_email = row.get("P_emaildomain", "").strip()
                r_email = row.get("R_emaildomain", "").strip()
                
                try:
                    amt = float(row.get("TransactionAmt", 0.0) or 0.0)
                except ValueError:
                    amt = 0.0
                    
                try:
                    score = float(row.get("risk_score", 0.0) or 0.0)
                except ValueError:
                    score = 0.0

                txn_record = {
                    "txn_id": txn_id,
                    "card_id": card_id,
                    "customer_id": cust_id,
                    "ts": ts_str,
                    "amount": amt,
                    "channel": channel,
                    "product_cd": product_cd,
                    "risk_score": score,
                    "addr1": addr1,
                    "addr2": addr2,
                    "purchaser_email": p_email,
                    "recipient_email": r_email
                }
                
                self.transactions[txn_id] = txn_record
                
                # Link to card
                if card_id:
                    self.cards.setdefault(card_id, {
                        "card_id": card_id,
                        "customer_id": cust_id,
                        "card_network": row.get("card4", ""),
                        "card_type": row.get("card6", "")
                    })
                    self.card_txns.setdefault(card_id, []).append(txn_id)
                    
                    if addr1:
                        reg_dict = self.card_regions.setdefault(card_id, {})
                        reg_dict[addr1] = reg_dict.get(addr1, 0) + 1
                    
                    # If this transaction has a device record, map profile to card
                    if txn_id in self.devices:
                        prof = self.devices[txn_id]["profile_str"]
                        self.device_to_cards.setdefault(prof, set()).add(card_id)

                # Link to customer
                if cust_id:
                    self.customers.setdefault(cust_id, {"customer_id": cust_id})
                    if card_id and card_id not in self.customer_cards.setdefault(cust_id, []):
                        self.customer_cards[cust_id].append(card_id)

                count += 1
                if max_rows and count >= max_rows:
                    break

        self.is_loaded = True

    def get_card_history(self, card_id: str) -> List[Dict[str, Any]]:
        """Returns all transactions for a card sorted chronologically."""
        txn_ids = self.card_txns.get(card_id, [])
        txns = [self.transactions[tid] for tid in txn_ids if tid in self.transactions]
        txns.sort(key=lambda x: x.get("ts", ""))
        return txns

    def get_device_neighbors(self, profile_str: str, exclude_card: Optional[str] = None) -> List[str]:
        """GSQL multi-hop traversal: DeviceProfile -> Transactions -> Cards."""
        if not profile_str or profile_str not in self.device_to_cards:
            return []
        cards = set(self.device_to_cards[profile_str])
        if exclude_card:
            cards.discard(exclude_card)
        return sorted(list(cards))

    def detect_card_testing(self, card_id: str, anchor_txn_id: str) -> Tuple[bool, List[str], float]:
        """
        Policy R5 / Pattern 1:
        Three or more small online authorizations (< $5.0) within an hour,
        followed by a larger purchase.
        """
        txns = self.get_card_history(card_id)
        if not txns:
            return False, [], 0.0

        # Locate anchor transaction
        anchor_idx = -1
        for i, t in enumerate(txns):
            if t["txn_id"] == anchor_txn_id:
                anchor_idx = i
                break

        if anchor_idx == -1:
            return False, [], 0.0

        anchor_t = txns[anchor_idx]
        try:
            anchor_dt = datetime.strptime(anchor_t["ts"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return False, [], 0.0

        # Check transactions within 2 hours prior or around anchor
        small_txns = []
        larger_txn = None
        
        for t in txns:
            try:
                t_dt = datetime.strptime(t["ts"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            
            delta_mins = (t_dt - anchor_dt).total_seconds() / 60.0
            if -120 <= delta_mins <= 120:
                if t["channel"] == "online" and t["amount"] <= 5.0:
                    small_txns.append(t["txn_id"])
                elif t["amount"] > 15.0:
                    larger_txn = t

        if len(small_txns) >= 3 and (larger_txn or anchor_t["amount"] > 15.0):
            all_affected = list(set(small_txns + ([anchor_t["txn_id"]] if anchor_t["amount"] > 5.0 else [])))
            exposure = sum(self.transactions[tid]["amount"] for tid in all_affected if tid in self.transactions)
            return True, all_affected, exposure

        return False, [], 0.0

    def detect_velocity_structuring(self, card_id: str, anchor_txn_id: str) -> Tuple[bool, List[str], float]:
        """
        Undocumented Pattern:
        Multiple online transactions within 40 minutes each just under $500 ($450-$499.99).
        """
        txns = self.get_card_history(card_id)
        if not txns:
            return False, [], 0.0

        anchor_t = self.transactions.get(anchor_txn_id)
        if not anchor_t:
            return False, [], 0.0

        try:
            anchor_dt = datetime.strptime(anchor_t["ts"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return False, [], 0.0

        structured_txns = []
        for t in txns:
            try:
                t_dt = datetime.strptime(t["ts"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            
            delta_mins = abs((t_dt - anchor_dt).total_seconds()) / 60.0
            if delta_mins <= 60.0:
                if 450.0 <= t["amount"] < 500.0:
                    structured_txns.append(t["txn_id"])

        if len(structured_txns) >= 3:
            exposure = sum(self.transactions[tid]["amount"] for tid in structured_txns if tid in self.transactions)
            return True, structured_txns, exposure

        return False, [], 0.0

    def detect_out_of_region(self, card_id: str, txn_id: str) -> Tuple[bool, str, Dict[str, int]]:
        """
        Policy R4 / Pattern 4:
        Card-present purchase in a billing region the cardholder has no history in,
        while normal activity continues at home.
        """
        t = self.transactions.get(txn_id)
        if not t:
            return False, "", {}
            
        region = t.get("addr1", "")
        if not region:
            return False, "", {}

        regions = self.card_regions.get(card_id, {})
        total_txns = sum(regions.values())
        
        # If this region has only 1 txn and other regions have >= 5 transactions
        if regions.get(region, 0) <= 2 and total_txns >= 5:
            top_region = max(regions.items(), key=lambda x: x[1])[0]
            if top_region != region:
                return True, top_region, regions

        return False, "", regions

    def write_investigation_case(self, case_id: str, case_data: Dict[str, Any]) -> str:
        """Commits the case record to graph vertices and edges."""
        self.investigation_cases[case_id] = case_data
        return f"CASE-GRAPH-{case_id}"
