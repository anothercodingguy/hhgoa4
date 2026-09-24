"""
Pattern Detector module for TigerGraph Agentic Fraud Investigation.
Classifies fraud patterns according to the five documented typologies,
identifies undocumented coordinated abuse (rings, structuring), or marks as none (legitimate).
"""
from typing import Dict, List, Any, Tuple

VALID_PATTERNS = [
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none"
]

class PatternDetector:
    def detect_pattern(self, context: Dict[str, Any]) -> Tuple[str, str, List[str], str, List[str], float]:
        """
        Analyzes GraphRAG context to determine pattern, description, affected txns,
        first suspicious txn, connected device profiles, and calculated exposure.
        Returns:
            (pattern, pattern_description, affected_txn_ids, first_suspicious_txn_id, connected_device_profiles, exposure_usd)
        """
        flagged_txn = context.get("flagged_txn", {})
        txn_id = flagged_txn.get("txn_id", "")
        amt = flagged_txn.get("amount", 0.0)
        channel = flagged_txn.get("channel", "in_person")
        identity = context.get("identity") or {}
        device_profile_str = context.get("device_profile_str", "")
        is_new_device = identity.get("is_new", False)
        proxy_flag = identity.get("proxy_flag", "")
        connected_cards = context.get("connected_cards", [])
        trigger_type = context.get("trigger", {}).get("type", "")
        trigger_text = context.get("trigger", {}).get("text", "")
        
        testing_res = context.get("testing_result", {})
        region_res = context.get("region_result", {})
        structuring_res = context.get("structuring_result", {})
        
        connected_devices = [device_profile_str] if device_profile_str and device_profile_str != "Unknown Device" else []

        # 1. Check for Card Testing (Pattern 1, Policy R5)
        if testing_res.get("detected"):
            affected = testing_res.get("affected_txn_ids", [txn_id])
            first_txn = affected[0] if affected else txn_id
            exposure = testing_res.get("exposure_usd", amt)
            return "card_testing", "", affected, first_txn, connected_devices, exposure

        # 2. Check for Undocumented Velocity Structuring (< $500 threshold evasion)
        if structuring_res.get("detected"):
            affected = structuring_res.get("affected_txn_ids", [txn_id])
            first_txn = affected[0] if affected else txn_id
            exposure = structuring_res.get("exposure_usd", amt)
            desc = (
                "Rapid velocity structuring: multiple online transactions executed within forty minutes, "
                "each specifically structured immediately below the $500 authorization limit to evade detection. "
                "Discovered via chronological velocity analysis on card."
            )
            return "undocumented", desc, affected, first_txn, connected_devices, exposure

        # 3. Check for Undocumented Syndicated Device / Proxy Ring (> 2 connected cards)
        if len(connected_cards) >= 2 and (is_new_device or proxy_flag):
            desc = (
                f"Syndicated device ring: online purchases conducted from a shared device profile "
                f"({device_profile_str}) operating behind an anonymous proxy, linking {len(connected_cards)} "
                f"different customer accounts across the graph. Pattern indicates coordinated credential misuse."
            )
            return "undocumented", desc, [txn_id], txn_id, connected_devices, amt

        # 4. Check for Out-of-Region Use (Pattern 4, Policy R2-R3)
        if region_res.get("is_out_of_region") and channel == "in_person":
            # Check if normal activity continues at home
            return "out_of_region_use", "", [txn_id], txn_id, [], amt

        # 5. Check for Account Takeover (Pattern 5)
        # Indicated by mixed channel transactions or customer dispute combined with identity/match anomalies
        if "compromised" in trigger_text.lower() or "takeover" in trigger_text.lower():
            return "account_takeover", "", [txn_id], txn_id, connected_devices, amt

        # 6. Check for Card-Not-Present from New Device (Pattern 3)
        if channel == "online" and is_new_device:
            return "card_not_present_new_device", "", [txn_id], txn_id, connected_devices, amt

        # 7. Check for Standard Card-Not-Present Fraud (Pattern 2)
        if channel == "online" and (trigger_type == "customer_report" or flagged_txn.get("risk_score", 0.0) >= 0.75):
            return "card_not_present_fraud", "", [txn_id], txn_id, connected_devices, amt

        # 8. Check for Analyst Request / Device Investigation (e.g. HHG-014)
        if trigger_type == "analyst_request" and connected_cards:
            desc = (
                f"Shared origin fraud cluster: transaction tied to unusual device fingerprint "
                f"({device_profile_str}) shared across {len(connected_cards)} other cardholders. "
                f"Coordinated card compromise discovered via graph neighborhood traversal."
            )
            return "undocumented", desc, [txn_id], txn_id, connected_devices, amt

        # Default fallback if suspicious
        if trigger_type == "customer_report":
            return "card_not_present_fraud", "", [txn_id], txn_id, connected_devices, amt

        # Otherwise none (legitimate)
        return "none", "", [], "", [], 0.0
