"""
Unit tests for Bank Fraud Policy v1.0 and Approval Routing Engine.
"""
import pytest
from src.graphrag.policy_corpus import ActionType, ApprovalRoute, get_approval_route, POLICY_RULES
from src.agent.next_best_action import NextBestActionEngine

def test_approval_routing_thresholds():
    # DECLINE_TRANSACTION -> L1
    assert get_approval_route(ActionType.DECLINE_TRANSACTION.value) == ApprovalRoute.L1.value

    # BLOCK_CARD <= $2,500 -> L1
    assert get_approval_route(ActionType.BLOCK_CARD.value, exposure_usd=2500.00) == ApprovalRoute.L1.value
    assert get_approval_route(ActionType.BLOCK_CARD.value, exposure_usd=150.00) == ApprovalRoute.L1.value

    # BLOCK_CARD > $2,500 -> L2
    assert get_approval_route(ActionType.BLOCK_CARD.value, exposure_usd=2500.01) == ApprovalRoute.L2.value
    assert get_approval_route(ActionType.BLOCK_CARD.value, exposure_usd=10000.00) == ApprovalRoute.L2.value

    # BLOCK_ALL_CARDS -> always L2
    assert get_approval_route(ActionType.BLOCK_ALL_CARDS.value) == ApprovalRoute.L2.value

    # FILE_REPORT -> always L2
    assert get_approval_route(ActionType.FILE_REPORT.value) == ApprovalRoute.L2.value

    # All others -> auto
    assert get_approval_route(ActionType.ALLOW_TRANSACTION.value) == ApprovalRoute.AUTO.value
    assert get_approval_route(ActionType.VERIFY_WITH_CUSTOMER.value) == ApprovalRoute.AUTO.value
    assert get_approval_route(ActionType.CREATE_CASE.value) == ApprovalRoute.AUTO.value
    assert get_approval_route(ActionType.MONITOR_CARD.value) == ApprovalRoute.AUTO.value
    assert get_approval_route(ActionType.CLOSE_NO_FRAUD.value) == ApprovalRoute.AUTO.value

def test_nba_engine_customer_denial():
    engine = NextBestActionEngine()
    context = {
        "trigger": {"type": "customer_report"},
        "flagged_txn": {"amount": 350.00},
        "connected_cards": ["C00888-K1"]
    }
    evidence_reqs = [{"type": "customer_validation", "assumed_response": "Customer denies making purchase."}]
    
    initial, final, what_changed = engine.determine_actions(
        context=context,
        pattern="card_not_present_fraud",
        initial_prob=0.74,
        final_prob=0.88,
        verdict="fraud",
        exposure_usd=350.00,
        evidence_requests=evidence_reqs
    )

    final_actions = [a["action"] for a in final]
    assert ActionType.BLOCK_CARD.value in final_actions
    assert ActionType.CREATE_CASE.value in final_actions
    assert ActionType.FILE_REPORT.value in final_actions
    assert ActionType.MONITOR_CONNECTED_CARDS.value in final_actions

    # Check approval route for BLOCK_CARD ($350 <= $2500 -> L1)
    block_action = next(a for a in final if a["action"] == ActionType.BLOCK_CARD.value)
    assert block_action["route"] == ApprovalRoute.L1.value

    # Check approval route for FILE_REPORT -> L2
    report_action = next(a for a in final if a["action"] == ActionType.FILE_REPORT.value)
    assert report_action["route"] == ApprovalRoute.L2.value
