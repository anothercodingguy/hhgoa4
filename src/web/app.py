"""
FastAPI Application Server for the TigerGraph Agentic Fraud Investigation Workbench.
Provides interactive APIs for case inspection, real-time graph visualization,
customer evidence simulation, and SAR filing document generation.
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from src.config import settings
from src.agent.core import FraudInvestigationAgent

app = FastAPI(title="TigerGraph Agentic Fraud Investigation Workbench", version="1.0.0")

# Mount static files directory
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared agent instance
_agent: Optional[FraudInvestigationAgent] = None

def get_agent() -> FraudInvestigationAgent:
    global _agent
    if _agent is None:
        _agent = FraudInvestigationAgent()
        _agent.mcp.client.ensure_data_loaded()
    return _agent

class InvestigateRequest(BaseModel):
    case_id: str
    flagged_txn_id: str
    card_id: str
    customer_id: str
    trigger_type: str
    trigger_text: str
    risk_score: Optional[float] = None
    override_customer_response: Optional[str] = None

@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>TigerGraph Fraud Investigation Workbench API Ready</h1>")

@app.get("/api/cases")
async def list_cases():
    """Lists all 20 benchmark cases and their execution statuses."""
    case_pack_file = settings.data_dir / "case_pack.csv"
    if not case_pack_file.exists():
        raise HTTPException(status_code=404, detail="case_pack.csv not found")

    cases_summary = []
    import csv
    with open(case_pack_file, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("case_id", "")
            json_path = settings.cases_dir / f"{cid}.json"
            status = "pending"
            verdict = "uninvestigated"
            exposure = 0.0
            sar_file = False
            pattern = ""

            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                        status = data.get("case", {}).get("status", "completed")
                        verdict = data.get("case", {}).get("verdict", "")
                        pattern = data.get("case", {}).get("pattern", "")
                        exposure = data.get("case", {}).get("exposure_usd", 0.0)
                        sar_file = data.get("sar", {}).get("file", False)
                except Exception:
                    pass

            cases_summary.append({
                "case_id": cid,
                "opened_at": row.get("opened_at", ""),
                "trigger_type": row.get("trigger_type", ""),
                "trigger_text": row.get("trigger_text", ""),
                "flagged_txn_id": row.get("flagged_txn_id", ""),
                "card_id": row.get("card_id", ""),
                "customer_id": row.get("customer_id", ""),
                "risk_score": float(row.get("risk_score")) if row.get("risk_score") else None,
                "status": status,
                "verdict": verdict,
                "pattern": pattern,
                "exposure_usd": exposure,
                "sar_file": sar_file
            })

    return cases_summary

@app.get("/api/cases/{case_id}")
async def get_case_detail(case_id: str):
    """Fetches complete investigation JSON answer for a specific case."""
    json_path = settings.cases_dir / f"{case_id}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Case {case_id} not yet investigated")

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/cases/{case_id}/graph")
async def get_case_graph(case_id: str):
    """Generates node-link graph visualization data for the case with rich node metadata."""
    json_path = settings.cases_dir / f"{case_id}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    with open(json_path, "r", encoding="utf-8") as f:
        cdata = json.load(f)

    nodes = []
    links = []

    case_obj = cdata.get("case", {})
    summary = case_obj.get("summary", "")
    cust_id = summary.split("Customer ")[-1].split(")")[0] if "Customer " in summary else "Customer"
    case_node_id = f"Case:{case_id}"
    verdict = case_obj.get("verdict", "uncertain")
    pattern = case_obj.get("pattern", "none")
    exposure = case_obj.get("exposure_usd", 0.0)
    prob = case_obj.get("fraud_probability", 0.0)

    # 1. Root Case Node
    nodes.append({
        "id": case_node_id,
        "label": case_id,
        "type": "case",
        "status": verdict,
        "data": {
            "case_id": case_id,
            "verdict": verdict,
            "pattern": pattern,
            "exposure_usd": f"${exposure:,.2f}",
            "fraud_probability": f"{int(prob * 100)}%",
            "status_label": case_obj.get("status", "open")
        }
    })

    # 2. Customer Node
    nodes.append({
        "id": f"Cust:{cust_id}",
        "label": cust_id,
        "type": "customer",
        "data": {
            "customer_id": cust_id,
            "kyc_tier": "Tier 2 Verified",
            "country": "US / IN Domestic",
            "relationship_since": "2015-04-12",
            "account_status": "Active Under Review" if verdict != "legitimate" else "In Good Standing"
        }
    })
    links.append({
        "source": case_node_id,
        "target": f"Cust:{cust_id}",
        "relation": "INVOLVES_CUSTOMER",
        "animated": False
    })

    # 3. Affected / Flagged Transactions
    for tid in case_obj.get("affected_txn_ids", []):
        t_node = f"Txn:{tid}"
        nodes.append({
            "id": t_node,
            "label": f"${tid}",
            "type": "transaction",
            "status": "fraud" if verdict == "fraud" else "flagged",
            "data": {
                "transaction_id": tid,
                "type": "Flagged Activity",
                "risk_contribution": "High Anomaly",
                "channel": "Online / Card-Not-Present"
            }
        })
        links.append({
            "source": case_node_id,
            "target": t_node,
            "relation": "AFFECTED_TXN",
            "animated": True
        })

    # 4. Connected Cards
    connected_cards = case_obj.get("connected_card_ids", [])
    # Limit max card nodes to avoid clutter if ring has 50+ cards, but preserve ring metrics
    display_cards = connected_cards[:12]
    for cid in display_cards:
        card_node = f"Card:{cid}"
        nodes.append({
            "id": card_node,
            "label": cid,
            "type": "card",
            "alert": True,
            "data": {
                "card_token": cid,
                "status": "Compromised Token" if verdict == "fraud" else "Under Surveillance",
                "network": "Visa / MC Signature",
                "ring_nexus": f"Part of {len(connected_cards)} card syndicate" if len(connected_cards) > 1 else "Primary Card"
            }
        })
        links.append({
            "source": case_node_id,
            "target": card_node,
            "relation": "CONNECTED_CARD",
            "animated": True if verdict == "fraud" else False
        })

    # 5. Connected Device Profiles
    for dev in case_obj.get("connected_device_profiles", []):
        dev_label = dev.split("|")[0].strip() if "|" in dev else dev[:20]
        dev_node = f"Dev:{dev_label}"
        nodes.append({
            "id": dev_node,
            "label": dev_label,
            "type": "device",
            "data": {
                "fingerprint": dev,
                "proxy_detected": "IP_PROXY:ANONYMOUS" in dev,
                "browser_os": dev.split("|")[1].strip() if "|" in dev and len(dev.split("|")) > 1 else "Android/Desktop",
                "shared_cards_count": len(connected_cards)
            }
        })
        links.append({
            "source": case_node_id,
            "target": dev_node,
            "relation": "FROM_DEVICE",
            "animated": True
        })

    # 6. Similar Prior Cases
    for sc in case_obj.get("similar_prior_cases", [])[:4]:
        sc_node = f"Prior:{sc}"
        nodes.append({
            "id": sc_node,
            "label": sc,
            "type": "prior_case",
            "data": {
                "historical_case_id": sc,
                "memory_source": "closed_cases_history.csv (TigerGraph Vector L2)",
                "relevance": "High Behavioral Similarity"
            }
        })
        links.append({
            "source": case_node_id,
            "target": sc_node,
            "relation": "SIMILAR_MEMORY",
            "animated": False
        })

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "total_nodes": len(nodes),
            "total_links": len(links),
            "ring_cards_total": len(connected_cards)
        }
    }

@app.get("/api/cases/{case_id}/timeline")
async def get_case_timeline(case_id: str):
    """Fetches chronological transaction timeline for the card under review."""
    case_pack_file = settings.data_dir / "case_pack.csv"
    if not case_pack_file.exists():
        raise HTTPException(status_code=404, detail="case_pack.csv not found")

    target_row = None
    import csv
    with open(case_pack_file, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("case_id") == case_id:
                target_row = row
                break

    if not target_row:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found in case pack")

    card_id = target_row.get("card_id", "")
    flagged_txn_id = target_row.get("flagged_txn_id", "")

    agent = get_agent()
    raw_txns = agent.mcp.client.get_card_history(card_id)

    # Read case JSON for affected list
    json_path = settings.cases_dir / f"{case_id}.json"
    affected_ids = set()
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                cdata = json.load(jf)
                affected_ids = set(str(x) for x in cdata.get("case", {}).get("affected_txn_ids", []))
        except Exception:
            pass

    timeline = []
    for t in raw_txns:
        tid = str(t.get("txn_id", ""))
        is_flagged = (tid == str(flagged_txn_id))
        is_affected = (tid in affected_ids)
        timeline.append({
            "txn_id": tid,
            "amount": float(t.get("amount", 0.0)),
            "ts": t.get("ts", ""),
            "channel": "online" if t.get("is_online") else "in_person",
            "is_flagged": is_flagged,
            "is_affected": is_affected,
            "dist1": t.get("dist1"),
            "addr1": t.get("addr1"),
            "risk_status": "CONFIRMED FRAUD" if is_affected else ("FLAGGED ALERT" if is_flagged else "NORMAL")
        })

    return {
        "case_id": case_id,
        "card_id": card_id,
        "flagged_txn_id": flagged_txn_id,
        "total_transactions": len(timeline),
        "timeline": timeline
    }

@app.post("/api/investigate")
async def run_investigation(req: InvestigateRequest):
    """Executes live investigation with optional customer simulation override."""
    agent = get_agent()
    result = agent.investigate(
        case_id=req.case_id,
        flagged_txn_id=req.flagged_txn_id,
        card_id=req.card_id,
        customer_id=req.customer_id,
        trigger_type=req.trigger_type,
        trigger_text=req.trigger_text,
        risk_score=req.risk_score,
        override_customer_response=req.override_customer_response
    )
    # Save back to file
    out_file = settings.cases_dir / f"{req.case_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result

@app.get("/api/stats")
async def get_overview_stats():
    """Provides high-level investigation metrics across all cases."""
    files = list(settings.cases_dir.glob("*.json"))
    total_cases = len(files)
    fraud_count = 0
    legit_count = 0
    uncertain_count = 0
    total_exposure = 0.0
    sar_filings = 0

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as jf:
                d = json.load(jf)
                v = d.get("case", {}).get("verdict", "")
                if v == "fraud":
                    fraud_count += 1
                elif v == "legitimate":
                    legit_count += 1
                else:
                    uncertain_count += 1
                total_exposure += d.get("case", {}).get("exposure_usd", 0.0)
                if d.get("sar", {}).get("file", False):
                    sar_filings += 1
        except Exception:
            pass

    return {
        "total_cases": total_cases,
        "fraud_confirmed": fraud_count,
        "cleared_legitimate": legit_count,
        "uncertain": uncertain_count,
        "total_exposure_usd": round(total_exposure, 2),
        "sar_filings_count": sar_filings
    }
