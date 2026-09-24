"""
Autonomous Continuous Exam Period Monitor & Proactive Alert Scanner.
Scans transactions during the November-December exam window for unflagged anomalous activity,
runs autonomous investigations, and saves cases in cases_beyond_exam/ for the Innovation bonus.
"""
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from src.config import settings
from src.agent.core import FraudInvestigationAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BEYOND_EXAM_DIR = settings.data_dir.parent.parent / "cases_beyond_exam"

def scan_exam_period_alerts(limit: int = 5) -> List[Dict[str, Any]]:
    BEYOND_EXAM_DIR.mkdir(parents=True, exist_ok=True)
    
    # Identify transactions already in the 20 exam cases
    case_pack_path = settings.data_dir / "case_pack.csv"
    exam_txns = set()
    if case_pack_path.exists():
        with open(case_pack_path, "r", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                exam_txns.add(r["flagged_txn_id"])

    logger.info("Initializing Agent for Continuous Exam Period Monitoring...")
    agent = FraudInvestigationAgent()
    agent.mcp.client.ensure_data_loaded()

    # Iterate directly over in-memory transactions (blazing fast)
    candidates = []
    for tid, txn in agent.mcp.client.local_graph.transactions.items():
        if tid in exam_txns:
            continue
        ts = txn.get("ts", "")
        # Exam period: Nov (2016-11) or Dec (2016-12)
        if "2016-11" in ts or "2016-12" in ts:
            score = float(txn.get("risk_score", 0.0) or 0.0)
            if score >= 0.88:
                candidates.append(txn)
                if len(candidates) >= limit:
                    break

    logger.info(f"Discovered {len(candidates)} unflagged real-time alert candidates in exam period.")
    
    results = []
    for i, txn in enumerate(candidates, 1):
        tid = txn["txn_id"]
        cust_id = txn.get("customer_id", "")
        card_id = txn.get("card_id", f"{cust_id}-K1")
        score = float(txn.get("risk_score", 0.0))
        amt = float(txn.get("amount", 0.0) or 0.0)
        case_id = f"HHG-AUTO-{i:03d}"
        trigger_text = f"Continuous monitor alert: transaction {tid} (${amt:.2f}, {txn.get('channel')}) scored at {score:.2f} during exam period."

        logger.info(f"Investigating proactive alert {case_id} (Txn: {tid}, Score: {score:.2f})...")
        res = agent.investigate(
            case_id=case_id,
            flagged_txn_id=tid,
            card_id=card_id,
            customer_id=cust_id,
            trigger_type="risk_score",
            trigger_text=trigger_text,
            risk_score=score
        )

        out_path = BEYOND_EXAM_DIR / f"{case_id}.json"
        with open(out_path, "w", encoding="utf-8") as out_f:
            json.dump(res, out_f, indent=2)

        results.append(res)
        logger.info(f"Persisted beyond-exam investigation -> {out_path.name} (Verdict: {res['case']['verdict']})")

    return results

if __name__ == "__main__":
    scan_exam_period_alerts(limit=5)
