"""
Case Memory module for TigerGraph Agentic Fraud Investigation.
Maintains and indexes historical closed cases (5,565 records) and supports dynamic writeback.
"""
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.config import settings

class CaseMemory:
    def __init__(self, csv_path: Optional[Path] = None):
        self.csv_path = csv_path or (settings.data_dir / "closed_cases_history.csv")
        self.cases: Dict[str, Dict[str, Any]] = {}
        self.cases_by_card: Dict[str, List[str]] = {}
        self.cases_by_customer: Dict[str, List[str]] = {}
        self.cases_by_pattern: Dict[str, List[str]] = {}
        self._load_memory()

    def _load_memory(self):
        if not self.csv_path.exists():
            return
        
        with open(self.csv_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                case_id = row.get("case_id", "").strip()
                if not case_id:
                    continue
                
                card_id = row.get("card_id", "").strip()
                customer_id = row.get("customer_id", "").strip()
                pattern = row.get("pattern", "none").strip()
                
                try:
                    exposure = float(row.get("exposure_usd", 0.0) or 0.0)
                except ValueError:
                    exposure = 0.0
                    
                record = {
                    "case_id": case_id,
                    "customer_id": customer_id,
                    "card_id": card_id,
                    "opened_at": row.get("opened_at", ""),
                    "closed_at": row.get("closed_at", ""),
                    "outcome": row.get("outcome", ""),
                    "pattern": pattern,
                    "first_fraud_txn_id": row.get("first_fraud_txn_id", ""),
                    "txn_ids": [t for t in row.get("txn_ids", "").split("|") if t],
                    "n_txns": int(row.get("n_txns", 0) or 0) if row.get("n_txns") else 0,
                    "exposure_usd": exposure,
                    "connected_card_ids": [c for c in row.get("connected_card_ids", "").split("|") if c and c != "nan"],
                    "actions_taken": row.get("actions_taken", ""),
                    "report_filed": row.get("report_filed", ""),
                    "analyst_notes": row.get("analyst_notes", "")
                }
                
                self.cases[case_id] = record
                
                if card_id:
                    self.cases_by_card.setdefault(card_id, []).append(case_id)
                if customer_id:
                    self.cases_by_customer.setdefault(customer_id, []).append(case_id)
                if pattern:
                    self.cases_by_pattern.setdefault(pattern, []).append(case_id)

    def find_similar_cases(
        self, 
        pattern: Optional[str] = None, 
        card_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        device_str: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieves similar past cases matching card, customer, device signature, or pattern.
        """
        matches = []
        seen = set()

        # 1. Exact card match in prior cases
        if card_id and card_id in self.cases_by_card:
            for cid in self.cases_by_card[card_id]:
                if cid not in seen:
                    matches.append((10, self.cases[cid]))
                    seen.add(cid)

        # 2. Customer match in prior cases
        if customer_id and customer_id in self.cases_by_customer:
            for cid in self.cases_by_customer[customer_id]:
                if cid not in seen:
                    matches.append((8, self.cases[cid]))
                    seen.add(cid)

        # 3. Device signature in analyst notes or connected cards
        if device_str and len(device_str) > 5:
            d_lower = device_str.lower()
            for cid, cdata in self.cases.items():
                if cid in seen:
                    continue
                notes_lower = cdata.get("analyst_notes", "").lower()
                if any(term in notes_lower for term in d_lower.split() if len(term) > 3):
                    matches.append((6, cdata))
                    seen.add(cid)
                    if len(matches) >= top_k * 2:
                        break

        # 4. Pattern match
        if pattern and pattern in self.cases_by_pattern:
            for cid in self.cases_by_pattern[pattern]:
                if cid not in seen:
                    matches.append((4, self.cases[cid]))
                    seen.add(cid)
                    if len(matches) >= top_k * 2:
                        break

        # Sort by relevance score descending
        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:top_k]]

    def write_case(self, case_dict: Dict[str, Any]) -> str:
        """
        Dynamically commits a newly investigated case into active case memory.
        """
        case_id = case_dict.get("case_id", f"CASE-DYN-{len(self.cases)+1:04d}")
        self.cases[case_id] = case_dict
        
        card_id = case_dict.get("card_id")
        if card_id:
            self.cases_by_card.setdefault(card_id, []).append(case_id)
        
        cust_id = case_dict.get("customer_id")
        if cust_id:
            self.cases_by_customer.setdefault(cust_id, []).append(case_id)
            
        pat = case_dict.get("pattern")
        if pat:
            self.cases_by_pattern.setdefault(pat, []).append(case_id)
            
        return case_id

    def count(self) -> int:
        return len(self.cases)
