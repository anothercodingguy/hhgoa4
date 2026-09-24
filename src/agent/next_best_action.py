"""
Next-Best Action (NBA) Policy Reasoner.
Evaluates pre-evidence and post-evidence policy actions and enforces approval routing.
"""
from typing import Dict, List, Any, Tuple
from src.graphrag.policy_corpus import ActionType, ApprovalRoute, get_approval_route

class NextBestActionEngine:
    def determine_actions(
        self,
        context: Dict[str, Any],
        pattern: str,
        initial_prob: float,
        final_prob: float,
        verdict: str,
        exposure_usd: float,
        evidence_requests: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], str]:
        """
        Determines initial actions, final actions, and the delta explanation ('what_changed').
        """
        trigger = context.get("trigger", {})
        trigger_type = trigger.get("type", "")
        connected_cards = context.get("connected_cards", [])
        flagged_txn = context.get("flagged_txn", {})
        amt = flagged_txn.get("amount", 0.0)

        initial_actions = []
        final_actions = []

        # ----------------------------------------------------------------------
        # 1. Compute Initial Next-Best Actions (Before Evidence Request)
        # ----------------------------------------------------------------------
        if pattern == "card_testing":
            # Rule R5
            initial_actions.append({
                "action": ActionType.DECLINE_TRANSACTION.value,
                "route": ApprovalRoute.L1.value,
                "reason": "R5: testing sequence observed, pending authorizations should be declined"
            })
            initial_actions.append({
                "action": ActionType.VERIFY_WITH_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": f"R1: initial probability {initial_prob:.2f} on pattern alone, confirm before blocking"
            })
        elif pattern == "undocumented":
            # Rule R9 & R6
            initial_actions.append({
                "action": ActionType.VERIFY_WITH_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R1: verify transaction authenticity while investigating coordinated ring"
            })
            if connected_cards:
                initial_actions.append({
                    "action": ActionType.MONITOR_CONNECTED_CARDS.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": f"R6: shared device links {len(connected_cards)} accounts across graph"
                })
        elif trigger_type == "customer_report":
            # Initial review of customer dispute
            initial_actions.append({
                "action": ActionType.VERIFY_WITH_CUSTOMER.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R1: confirm customer dispute and check whether card is still in customer possession"
            })
            initial_actions.append({
                "action": ActionType.MONITOR_CARD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "Heighten monitoring sensitivity pending verification"
            })
        else: # risk_score or out_of_region
            if initial_prob >= 0.70:
                initial_actions.append({
                    "action": ActionType.STEP_UP_AUTH.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": "R1: elevated model risk requires step-up authentication before completion"
                })
            else:
                initial_actions.append({
                    "action": ActionType.VERIFY_WITH_CUSTOMER.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": f"R1: weak single signal (probability {initial_prob:.2f}), verify before blocking"
                })

        # ----------------------------------------------------------------------
        # 2. Compute Final Next-Best Actions (After Assumed Evidence Response)
        # ----------------------------------------------------------------------
        if not evidence_requests:
            final_actions = list(initial_actions)
            what_changed = "nothing"
        elif verdict == "legitimate":
            final_actions.append({
                "action": ActionType.CLOSE_NO_FRAUD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R3: customer confirmed the transaction; alert cleared"
            })
            what_changed = f"Cardholder validation confirmed legitimate activity; probability dropped from {initial_prob:.2f} to {final_prob:.2f}, allowing alert closure without blocking."
        elif verdict == "fraud":
            # Block card routing based on exposure
            block_route = ApprovalRoute.L1.value if exposure_usd <= 2500.0 else ApprovalRoute.L2.value
            final_actions.append({
                "action": ActionType.BLOCK_CARD.value,
                "route": block_route,
                "reason": f"R2: customer denied transaction; exposure ${exposure_usd:.2f} requires {block_route} approval"
            })
            final_actions.append({
                "action": ActionType.CREATE_CASE.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R2: internal case opened and written to graph memory"
            })
            
            # SAR filing check (Rule R2, R6, R9, or exposure > 1000)
            needs_report = (
                exposure_usd >= 1000.0 
                or len(connected_cards) >= 1 
                or pattern in ("undocumented", "card_testing")
            )
            if needs_report:
                report_reason = "R2: confirmed unauthorized use"
                if exposure_usd >= 1000.0:
                    report_reason += f" exceeding $1,000 exposure threshold (${exposure_usd:.2f})"
                if len(connected_cards) >= 1:
                    report_reason += f" and linked via shared device to {len(connected_cards)} other compromised accounts"
                if pattern == "undocumented":
                    report_reason = "R9: coordinated undocumented pattern with multi-card compromise"
                
                final_actions.append({
                    "action": ActionType.FILE_REPORT.value,
                    "route": ApprovalRoute.L2.value,
                    "reason": report_reason
                })

            if connected_cards:
                final_actions.append({
                    "action": ActionType.MONITOR_CONNECTED_CARDS.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": f"R6: device profile shared with {len(connected_cards)} other cardholders"
                })

            what_changed = (
                f"Customer validation denial confirmed unauthorized status, raising probability from {initial_prob:.2f} to {final_prob:.2f}. "
                f"Initial verification escalated to BLOCK_CARD ({block_route}), CREATE_CASE, and "
                f"{'FILE_REPORT (L2)' if needs_report else 'monitoring'}."
            )
        else: # uncertain
            final_actions.append({
                "action": ActionType.DECLINE_TRANSACTION.value,
                "route": ApprovalRoute.L1.value,
                "reason": "R4: pending authorization declined due to unresolved ambiguity"
            })
            final_actions.append({
                "action": ActionType.MONITOR_CARD.value,
                "route": ApprovalRoute.AUTO.value,
                "reason": "R4: card placed on 72-hour heightened monitoring"
            })
            if exposure_usd >= 500.0:
                final_actions.append({
                    "action": ActionType.ESCALATE_TO_ANALYST.value,
                    "route": ApprovalRoute.AUTO.value,
                    "reason": f"R8: uncertain verdict with exposure ${exposure_usd:.2f} exceeding $500"
                })
            what_changed = f"Verification inconclusive; probability remains {final_prob:.2f}. Precautionary decline and monitoring enacted per R4/R8."

        return initial_actions, final_actions, what_changed
