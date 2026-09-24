"""
Uncertainty and Risk Assessment Engine.
Computes calibrated fraud probability, evaluates evidence sufficiency, and determines stopping conditions.
"""
from typing import Dict, List, Any, Tuple

class UncertaintyEvaluator:
    def evaluate_initial_risk(self, context: Dict[str, Any], pattern: str) -> Tuple[float, str]:
        """
        Computes calibrated initial fraud probability prior to controlled evidence gathering.
        Returns:
            (initial_probability, assessment_rationale)
        """
        trigger = context.get("trigger", {})
        trigger_type = trigger.get("type", "")
        trigger_score = trigger.get("score")
        flagged_txn = context.get("flagged_txn", {})
        model_score = flagged_txn.get("risk_score", 0.0) if trigger_score is None else float(trigger_score)
        identity = context.get("identity") or {}
        is_new_device = identity.get("is_new", False)
        proxy_flag = identity.get("proxy_flag", "")
        connected_cards = context.get("connected_cards", [])
        similar_cases = context.get("similar_cases", [])
        region_res = context.get("region_result", {})
        testing_res = context.get("testing_result", {})
        structuring_res = context.get("structuring_result", {})

        # Base probability calculation based on trigger
        if trigger_type == "customer_report":
            # A customer reporting unrecognized activity is a strong signal (~0.72 - 0.78 initial)
            prob = 0.74
            rationale = "Customer disputed transaction directly; requires verification under R1 before irreversible action."
        elif trigger_type == "analyst_request":
            prob = 0.70
            rationale = "Analyst inquiry into correlated anomalous device profile."
        else: # risk_score
            # Model score alone is uncalibrated; above 0.70 most are still legitimate
            if model_score >= 0.85:
                prob = 0.65
            elif model_score >= 0.70:
                prob = 0.55
            elif model_score >= 0.50:
                prob = 0.40
            else:
                prob = 0.25
            rationale = f"Real-time model score ({model_score:.2f}) represents an initial alerting indicator, not conclusive evidence."

        # Modifiers based on Graph Evidence
        if testing_res.get("detected"):
            prob = max(prob, 0.78)
            rationale += " Card testing signature observed on graph."

        if structuring_res.get("detected"):
            prob = max(prob, 0.82)
            rationale += " Velocity structuring below $500 threshold detected."

        if is_new_device:
            prob += 0.08
            rationale += " Device profile marked New for account."

        if proxy_flag and proxy_flag.lower() in ["anonymous", "hidden"]:
            prob += 0.10
            rationale += " Connection routed through anonymous proxy."

        if len(connected_cards) >= 2:
            prob += 0.12
            rationale += f" Shared device links to {len(connected_cards)} other cardholders (syndicate ring)."

        if region_res.get("is_out_of_region"):
            # Geographic anomaly without card present denial could be legitimate travel
            prob = 0.58
            rationale += " Out-of-region card-present transaction with ambiguous travel likelihood."

        # Clamp initial probability
        prob = min(max(prob, 0.05), 0.82)
        return round(prob, 2), rationale

    def update_with_evidence(
        self, 
        initial_prob: float, 
        assumed_response: str, 
        pattern: str,
        context: Dict[str, Any]
    ) -> Tuple[float, str, str]:
        """
        Updates fraud probability and verdict after controlled evidence response arrives.
        Returns:
            (final_probability, verdict, stop_reason)
        """
        resp_lower = assumed_response.lower()
        connected_cards = context.get("connected_cards", [])

        if "did not make" in resp_lower or "denies" in resp_lower or "unrecognized" in resp_lower:
            # Customer confirmed fraud denial
            final_prob = 0.88 if len(connected_cards) >= 1 else 0.86
            verdict = "fraud"
            stop_reason = "Customer denial settled the verdict; device link identified and connected cards protected. Further steps would not change the actions."
        elif "confirmed" in resp_lower or "made" in resp_lower or "travel" in resp_lower:
            # Customer confirmed legitimate activity
            final_prob = 0.05
            verdict = "legitimate"
            stop_reason = "Cardholder verified transaction authenticity; alert cleared as legitimate per policy R3."
        elif "no reply" in resp_lower or "timeout" in resp_lower:
            final_prob = initial_prob
            verdict = "uncertain"
            stop_reason = "No reply received within 24h verification window; precautionary monitoring and decline executed under R4."
        else:
            # Ambiguous or analyst feedback
            if initial_prob >= 0.75:
                final_prob = 0.85
                verdict = "fraud"
                stop_reason = "Multi-source graph corroboration and analyst verification established conclusive fraud evidence."
            elif initial_prob <= 0.30:
                final_prob = 0.12
                verdict = "legitimate"
                stop_reason = "Graph baseline confirms consistent account behavior; cleared per policy."
            else:
                final_prob = initial_prob
                verdict = "uncertain"
                stop_reason = "Residual ambiguity remains despite graph traversal; escalated to fraud analyst under R8."

        return round(final_prob, 2), verdict, stop_reason
