"""
TigerGraph Model Context Protocol (MCP) Tools.
Exposes graph traversal, pattern detection, and case memory capabilities as tools.
"""
from typing import Dict, List, Any, Optional
from src.tigergraph_engine.client import TigerGraphClient
from src.graphrag.case_memory import CaseMemory

class TigerGraphMCPTools:
    def __init__(self, tg_client: Optional[TigerGraphClient] = None, case_memory: Optional[CaseMemory] = None):
        self.client = tg_client or TigerGraphClient()
        self.memory = case_memory or CaseMemory()

    def get_transaction(self, txn_id: str) -> Dict[str, Any]:
        """Fetch transaction attributes from the graph."""
        res = self.client.get_transaction(txn_id)
        return res or {"error": f"Transaction {txn_id} not found"}

    def get_identity(self, txn_id: str) -> Dict[str, Any]:
        """Fetch online device and identity record for transaction."""
        res = self.client.get_identity(txn_id)
        return res or {"error": f"No online identity record for transaction {txn_id}"}

    def get_card_history(self, card_id: str) -> List[Dict[str, Any]]:
        """Fetch all chronological transactions associated with card."""
        return self.client.get_card_history(card_id)

    def get_device_neighbors(self, profile_str: str, exclude_card: Optional[str] = None) -> List[str]:
        """Traverse graph to find other cards that share the exact device profile."""
        return self.client.get_device_neighbors(profile_str, exclude_card)

    def detect_card_testing(self, card_id: str, anchor_txn_id: str) -> Dict[str, Any]:
        """Detect rapid sub-$5 authorizations followed by larger purchase on card."""
        detected, affected, exposure = self.client.detect_card_testing(card_id, anchor_txn_id)
        return {
            "detected": detected,
            "affected_txn_ids": affected,
            "exposure_usd": exposure
        }

    def detect_velocity_structuring(self, card_id: str, anchor_txn_id: str) -> Dict[str, Any]:
        """Detect coordinated burst of transactions structured just below $500."""
        detected, affected, exposure = self.client.detect_velocity_structuring(card_id, anchor_txn_id)
        return {
            "detected": detected,
            "affected_txn_ids": affected,
            "exposure_usd": exposure
        }

    def detect_out_of_region(self, card_id: str, txn_id: str) -> Dict[str, Any]:
        """Analyze geographic distribution of transactions on card."""
        drift, top_region, dist = self.client.detect_out_of_region(card_id, txn_id)
        return {
            "is_out_of_region": drift,
            "home_region": top_region,
            "region_distribution": dist
        }

    def find_similar_cases(
        self, 
        pattern: Optional[str] = None, 
        card_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        device_str: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Query case memory for closed cases matching pattern, card, or device."""
        return self.memory.find_similar_cases(pattern, card_id, customer_id, device_str, top_k)

    def write_case_to_graph(self, case_id: str, case_data: Dict[str, Any]) -> str:
        """Write investigation case node and associated edges to TigerGraph."""
        gid = self.client.write_investigation_case(case_id, case_data)
        self.memory.write_case(case_data)
        return gid
