"""
Master Pipeline Runner for the 20 Benchmark Cases (HHGOA 2026).
Iterates over case_pack.csv, executes the FraudInvestigationAgent on all 20 cases,
and persists verified JSON answer files into cases/<case_id>.json.
"""
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from src.config import settings
from src.agent.core import FraudInvestigationAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_benchmark_cases(output_dir: Path = settings.cases_dir) -> List[Dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    case_pack_path = settings.data_dir / "case_pack.csv"

    if not case_pack_path.exists():
        raise FileNotFoundError(f"case_pack.csv not found at {case_pack_path}")

    logger.info("Initializing Fraud Investigation Agent...")
    agent = FraudInvestigationAgent()
    agent.mcp.client.ensure_data_loaded()

    results = []
    with open(case_pack_path, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        cases = list(reader)

    logger.info(f"Loaded {len(cases)} benchmark cases from case_pack.csv.")
    
    for row in cases:
        case_id = row.get("case_id", "").strip()
        flagged_txn_id = row.get("flagged_txn_id", "").strip()
        card_id = row.get("card_id", "").strip()
        customer_id = row.get("customer_id", "").strip()
        trigger_type = row.get("trigger_type", "").strip()
        trigger_text = row.get("trigger_text", "").strip()
        risk_score_str = row.get("risk_score", "").strip()
        risk_score = float(risk_score_str) if risk_score_str else None

        logger.info(f"Investigating {case_id} (Trigger: {trigger_type}, Txn: {flagged_txn_id})...")
        answer = agent.investigate(
            case_id=case_id,
            flagged_txn_id=flagged_txn_id,
            card_id=card_id,
            customer_id=customer_id,
            trigger_type=trigger_type,
            trigger_text=trigger_text,
            risk_score=risk_score
        )

        out_file = output_dir / f"{case_id}.json"
        with open(out_file, "w", encoding="utf-8") as out_f:
            json.dump(answer, out_f, indent=2)

        results.append(answer)
        logger.info(
            f"Completed {case_id}: Verdict={answer['case']['verdict']}, "
            f"Pattern={answer['case']['pattern']}, Exposure=${answer['case']['exposure_usd']:.2f}, "
            f"SAR={answer['sar']['file']}, Saved -> {out_file.name}"
        )

    logger.info(f"Successfully processed and saved all {len(results)} benchmark case files.")
    return results

if __name__ == "__main__":
    run_benchmark_cases()
