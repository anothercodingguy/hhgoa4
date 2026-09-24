"""
Bank Fraud Policy v1.0 Corpus and Approval Routing Engine.
Encodes exact rules R1 to R10, authorized actions, and approval constraints.
"""
from typing import List, Dict, Any, Tuple
from enum import Enum

class ActionType(str, Enum):
    ALLOW_TRANSACTION = "ALLOW_TRANSACTION"
    DECLINE_TRANSACTION = "DECLINE_TRANSACTION"
    MONITOR_CARD = "MONITOR_CARD"
    MONITOR_CONNECTED_CARDS = "MONITOR_CONNECTED_CARDS"
    WARN_CUSTOMER = "WARN_CUSTOMER"
    VERIFY_WITH_CUSTOMER = "VERIFY_WITH_CUSTOMER"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    BLOCK_CARD = "BLOCK_CARD"
    BLOCK_ALL_CARDS = "BLOCK_ALL_CARDS"
    GENERATE_REPORT = "GENERATE_REPORT"
    CREATE_CASE = "CREATE_CASE"
    FILE_REPORT = "FILE_REPORT"
    ESCALATE_TO_ANALYST = "ESCALATE_TO_ANALYST"
    CLOSE_NO_FRAUD = "CLOSE_NO_FRAUD"

class ApprovalRoute(str, Enum):
    AUTO = "auto"
    L1 = "L1"   # Team lead
    L2 = "L2"   # Fraud manager

def get_approval_route(action: str, exposure_usd: float = 0.0) -> str:
    """
    Computes required approval route according to Section 2 of Fraud Policy v1.0.
    """
    if action == ActionType.DECLINE_TRANSACTION.value:
        return ApprovalRoute.L1.value
    elif action == ActionType.BLOCK_CARD.value:
        return ApprovalRoute.L1.value if exposure_usd <= 2500.0 else ApprovalRoute.L2.value
    elif action in (ActionType.BLOCK_ALL_CARDS.value, ActionType.FILE_REPORT.value):
        return ApprovalRoute.L2.value
    else:
        return ApprovalRoute.AUTO.value

POLICY_RULES: Dict[str, Dict[str, str]] = {
    "R1": {
        "title": "Verify before you block on a weak signal",
        "description": "If the case rests on a single signal (including a risk score alone) and assessed fraud probability is below 0.70, recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block. Blocking a legitimate customer on one signal is a policy breach."
    },
    "R2": {
        "title": "Customer denies the transaction",
        "description": "Recommend BLOCK_CARD and CREATE_CASE. Add FILE_REPORT if exposure exceeds $1,000 or the case connects to a shared device profile or another card's fraud."
    },
    "R3": {
        "title": "Customer confirms the transaction",
        "description": "Recommend CLOSE_NO_FRAUD. Note the confirmation in the case file."
    },
    "R4": {
        "title": "No reply within 24 hours",
        "description": "Recommend MONITOR_CARD and DECLINE_TRANSACTION for pending authorizations. Escalate if exposure exceeds $500."
    },
    "R5": {
        "title": "Card testing",
        "description": "Three or more small online authorizations on one card within an hour, followed by a larger purchase: recommend DECLINE_TRANSACTION and STEP_UP_AUTH. If a purchase over $100 has already cleared, recommend BLOCK_CARD."
    },
    "R6": {
        "title": "Shared origin",
        "description": "When several cards show fraud from the same device profile, the same billing region, or the same recipient email in one window, name the shared element, recommend CREATE_CASE and FILE_REPORT, and MONITOR_CONNECTED_CARDS for every card that shares it."
    },
    "R7": {
        "title": "Disputed but legitimate",
        "description": "When the customer disputes a charge that matches their own recurring pattern (same merchant, same amount, monthly), recommend CREATE_CASE, VERIFY_WITH_CUSTOMER, and WARN_CUSTOMER. Do not block."
    },
    "R8": {
        "title": "Escalate when uncertain and exposed",
        "description": "If the verdict is uncertain and exposure exceeds $500, or the evidence conflicts, recommend ESCALATE_TO_ANALYST."
    },
    "R9": {
        "title": "Undocumented patterns",
        "description": "When activity fits none of the known patterns but the evidence shows coordinated or repeated abuse across customers, recommend CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST, and describe the pattern in your own words. Do not force it into a known category."
    },
    "R10": {
        "title": "Never BLOCK_ALL_CARDS",
        "description": "Never BLOCK_ALL_CARDS unless at least two of the customer's cards show confirmed fraud or the customer's credentials are confirmed compromised."
    }
}
