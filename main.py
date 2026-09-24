"""
Main Entry Point for TigerGraph Agentic Fraud Investigation System (HHGOA 2026).
Supports CLI case investigation, benchmark execution, and web dashboard hosting.
"""
import argparse
import sys
import uvicorn
from pathlib import Path
from src.config import settings
from src.pipeline import run_benchmark_cases
from src.agent.core import FraudInvestigationAgent

def main():
    parser = argparse.ArgumentParser(description="TigerGraph Agentic Fraud Investigation System (HHGOA 2026)")
    parser.add_argument("--benchmark", action="store_true", help="Execute agent on all 20 benchmark cases in case_pack.csv")
    parser.add_argument("--serve", action="store_true", help="Launch interactive analyst workbench web server")
    parser.add_argument("--port", type=int, default=8000, help="Port for web dashboard server (default: 8000)")
    parser.add_argument("--case", type=str, default=None, help="Investigate a specific case ID (e.g. HHG-014)")

    args = parser.parse_args()

    if args.serve:
        print(f"🚀 Starting TigerGraph Fraud Investigation Workbench at http://127.0.0.1:{args.port}...")
        uvicorn.run("src.web.app:app", host="0.0.0.0", port=args.port, reload=False)
    elif args.benchmark:
        print("⚡ Executing 20 Benchmark Cases from case_pack.csv...")
        run_benchmark_cases()
    elif args.case:
        import csv, json
        case_pack = settings.data_dir / "case_pack.csv"
        found = False
        with open(case_pack, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                if row["case_id"] == args.case:
                    found = True
                    agent = FraudInvestigationAgent()
                    print(f"🔍 Investigating {args.case}...")
                    res = agent.investigate(
                        case_id=row["case_id"],
                        flagged_txn_id=row["flagged_txn_id"],
                        card_id=row["card_id"],
                        customer_id=row["customer_id"],
                        trigger_type=row["trigger_type"],
                        trigger_text=row["trigger_text"],
                        risk_score=float(row["risk_score"]) if row["risk_score"] else None
                    )
                    print(json.dumps(res, indent=2))
                    break
        if not found:
            print(f"❌ Case {args.case} not found in case_pack.csv")
    else:
        # Default action: run benchmark then suggest launching dashboard
        print("⚡ No flags specified. Executing 20 Benchmark Cases...")
        run_benchmark_cases()
        print("\n🎉 Benchmark completed. To launch the interactive analyst dashboard, run:\n   python main.py --serve\n")

if __name__ == "__main__":
    main()
