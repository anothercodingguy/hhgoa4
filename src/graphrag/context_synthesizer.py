"""
GraphRAG Context Synthesizer module.
Fuses Knowledge Graph evidence, Historical Case Memory, and Fraud Policies into structured,
high-signal context for agent reasoning and next-best action recommendation.
"""
from typing import Dict, List, Any, Optional
from src.graphrag.policy_corpus import POLICY_RULES, get_approval_route
from src.graphrag.regulatory_corpus import REGULATORY_GUIDANCE

class GraphRAGContextSynthesizer:
    def __init__(self, mcp_tools):
        self.mcp = mcp_tools

    def synthesize_context(
        self,
        case_id: str,
        flagged_txn_id: str,
        card_id: str,
        customer_id: str,
        trigger_type: str,
        trigger_text: str,
        initial_risk_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes multi-dimensional graph retrieval to build comprehensive GraphRAG context.
        """
        # 1. Fetch Flagged Transaction Details
        txn = self.mcp.get_transaction(flagged_txn_id)
        
        # 2. Fetch Identity / Device profile
        identity = self.mcp.get_identity(flagged_txn_id)
        has_identity = "error" not in identity
        device_profile_str = identity.get("profile_str", "") if has_identity else ""
        is_new_device = identity.get("is_new", False) if has_identity else False
        proxy_flag = identity.get("proxy_flag", "") if has_identity else ""

        # 3. Card History & Baselines
        card_history = self.mcp.get_card_history(card_id)
        total_card_txns = len(card_history)
        avg_amount = sum(t["amount"] for t in card_history) / max(total_card_txns, 1)

        # 4. Multi-hop Graph Traversal: Device Sharing (Fraud Ring)
        connected_cards = []
        if device_profile_str and device_profile_str != "Unknown Device":
            connected_cards = self.mcp.get_device_neighbors(device_profile_str, exclude_card=card_id)

        # 5. Pattern Detection Algorithms
        testing_result = self.mcp.detect_card_testing(card_id, flagged_txn_id)
        region_result = self.mcp.detect_out_of_region(card_id, flagged_txn_id)
        structuring_result = self.mcp.detect_velocity_structuring(card_id, flagged_txn_id)

        # 6. Retrieve Similar Past Cases from Case Memory
        similar_cases = self.mcp.find_similar_cases(
            card_id=card_id,
            customer_id=customer_id,
            device_str=device_profile_str if device_profile_str else None,
            top_k=4
        )
        similar_case_ids = [c["case_id"] for c in similar_cases]

        # 7. Synthesize Grounding Narrative
        evidence_items = []
        
        if txn and "error" not in txn:
            evidence_items.append({
                "claim": f"Flagged transaction {flagged_txn_id}: ${txn['amount']:.2f} ({txn['channel']}) with model risk score {txn['risk_score']:.2f}",
                "source": "graph",
                "ref": f"query:get_transaction(txn_id={flagged_txn_id})",
                "entity_ids": [flagged_txn_id, card_id]
            })

        if has_identity:
            evidence_items.append({
                "claim": f"Transaction originated from device '{device_profile_str}', marked is_new={is_new_device}, proxy={proxy_flag or 'none'}",
                "source": "graph",
                "ref": f"query:get_identity(txn_id={flagged_txn_id})",
                "entity_ids": [flagged_txn_id]
            })

        if connected_cards:
            evidence_items.append({
                "claim": f"Device profile shared across {len(connected_cards)} other cards in the graph: {', '.join(connected_cards[:3])}",
                "source": "graph",
                "ref": "query:get_device_neighbors",
                "entity_ids": connected_cards[:5]
            })

        if testing_result["detected"]:
            evidence_items.append({
                "claim": f"Card testing signature detected: 3+ small authorizations (< $5) followed by larger transaction. Exposure: ${testing_result['exposure_usd']:.2f}",
                "source": "graph",
                "ref": "query:detect_card_testing",
                "entity_ids": testing_result["affected_txn_ids"]
            })

        if structuring_result["detected"]:
            evidence_items.append({
                "claim": f"Velocity structuring signature detected: burst of online purchases structured just below $500 threshold within 40 minutes. Exposure: ${structuring_result['exposure_usd']:.2f}",
                "source": "graph",
                "ref": "query:detect_velocity_structuring",
                "entity_ids": structuring_result["affected_txn_ids"]
            })

        if region_result["is_out_of_region"]:
            evidence_items.append({
                "claim": f"Geographic drift: Card present in billing region {txn.get('addr1')} with no prior history (home region {region_result['home_region']})",
                "source": "graph",
                "ref": "query:detect_out_of_region",
                "entity_ids": [flagged_txn_id, card_id]
            })

        if similar_cases:
            for sc in similar_cases[:2]:
                sc_outcome = sc.get("outcome") or sc.get("verdict") or "resolved"
                sc_pattern = sc.get("pattern") or "unclassified"
                sc_notes = sc.get("analyst_notes") or ""
                evidence_items.append({
                    "claim": f"Corroborating case memory {sc.get('case_id', 'HIST')}: {sc_outcome} ({sc_pattern}) - {sc_notes[:120]}...",
                    "source": "document",
                    "ref": f"closed_case:{sc.get('case_id', 'HIST')}",
                    "entity_ids": [sc.get("case_id", "HIST")]
                })

        return {
            "case_id": case_id,
            "card_id": card_id,
            "customer_id": customer_id,
            "flagged_txn": txn,
            "identity": identity if has_identity else None,
            "device_profile_str": device_profile_str,
            "connected_cards": connected_cards,
            "testing_result": testing_result,
            "region_result": region_result,
            "structuring_result": structuring_result,
            "similar_cases": similar_cases,
            "similar_case_ids": similar_case_ids,
            "evidence_items": evidence_items,
            "baseline": {
                "total_txns": total_card_txns,
                "avg_amount": avg_amount
            },
            "trigger": {
                "type": trigger_type,
                "text": trigger_text,
                "score": initial_risk_score
            }
        }
