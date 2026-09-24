# hhgoa4 - TigerGraph Fraud Investigation Engine

An automated fraud investigation agent and analyst workbench for the **Hacker House Goa 2026** challenge (Track #4: Agentic Fraud Investigation & Next-Best Action). Built on **TigerGraph** (GSQL + graph engine), **Model Context Protocol (MCP)**, and **GraphRAG** to investigate suspicious transactions from the IEEE-CIS Fraud Detection dataset (590k+ transactions, 144k+ identity records, and 5,565 historical closed cases).

---

## Overview

Traditional fraud scoring models flag individual transactions with risk scores, but cannot explain network-level coordination. Fraud analysts must manually cross-reference card numbers, IP/device fingerprints, billing regions, and policy manuals before taking action.

This system automates that investigation loop:
1. **Graph Traversal (TigerGraph)**: Uncovers multi-hop device sharing rings, card-testing micro-authorization bursts, and rapid geographic drift across the 590,742 transaction graph.
2. **MCP Tool Layer**: Exposes graph queries, historical case retrieval, and policy lookups as standardized Model Context Protocol tools.
3. **GraphRAG Reasoning**: Synthesizes connected subgraphs, Bank Fraud Policy v1.0 rules (R1-R10), and 5,565 historical closed cases to calibrate fraud probability.
4. **Next-Best Action & Approval Routing**: Recommends actions before and after gathering customer validation evidence, enforcing strict governance (Auto, L1 Team Lead, L2 Fraud Manager) and documenting the exact delta.
5. **Regulatory Compliance (FinCEN SAR)**: Automatically drafts 6-12 sentence Suspicious Activity Reports (SAR Form 111) answering Who, What, When, Where, How, and Why for cases meeting filing criteria.
6. **Case Memory Writeback**: Commits resolved cases back into TigerGraph as new vertices to protect future transactions.

---

## Repository Structure

```
hhgoa4/
├── cases/                     # 20 benchmark case JSON evaluations (HHG-001 to HHG-020)
├── data/
│   └── HHGOA_IEEE/            # IEEE-CIS dataset files
│       ├── transactions.csv   # 590,742 card transactions
│       ├── identity.csv       # 144,432 online identity records
│       ├── closed_cases_history.csv # 5,565 closed historical cases
│       ├── case_pack.csv      # 20 benchmark exam alerts
│       └── README.md          # Dataset & policy specifications
├── tigergraph/
│   ├── schema.gsql            # TigerGraph DDL schema (vertices & edges)
│   ├── load_data.gsql         # GSQL loading jobs for IEEE-CIS data
│   └── queries.gsql           # GSQL queries (device sharing, card testing, geo drift)
├── src/
│   ├── config.py              # Configuration & policy thresholds
│   ├── pipeline.py            # End-to-end benchmark evaluation pipeline
│   ├── tigergraph_engine/
│   │   ├── client.py          # Savanna Cloud pyTigerGraph client & fallback
│   │   └── in_memory_graph.py # Fast local graph engine for deterministic grading
│   ├── tigergraph_mcp/
│   │   ├── server.py          # TigerGraph MCP server implementation
│   │   └── tools.py           # 8 standard MCP tools for graph traversal & memory
│   ├── graphrag/
│   │   ├── policy_corpus.py   # Bank Fraud Policy v1.0 rules (R1-R10) & routing
│   │   ├── regulatory_corpus.py # FinCEN SAR & FATF regulatory guidance
│   │   ├── case_memory.py     # 5,565 historical closed case retrieval & writeback
│   │   └── context_synthesizer.py # Multi-source context aggregator
│   ├── agent/
│   │   ├── core.py            # Master investigation orchestrator
│   │   ├── pattern_detector.py # Graph pattern recognition (Rings, Testing, CNP)
│   │   ├── uncertainty.py     # Calibrated probability & stopping rules
│   │   ├── next_best_action.py # Initial vs final NBA reasoner & delta tracker
│   │   └── sar_generator.py   # FinCEN SAR Form 111 narrative generator
│   └── web/
│       ├── app.py             # FastAPI backend for analyst workbench
│       └── static/            # Clean workbench UI (HTML, CSS, JS)
├── tests/
│   ├── test_graph_engine.py   # Graph traversal unit tests
│   ├── test_policy_nba.py     # Policy rules and approval route tests
│   └── test_benchmark_cases.py# Schema validation for all 20 benchmark JSONs
├── main.py                    # CLI entrypoint (--benchmark, --serve, --test)
├── requirements.txt           # Python dependencies
├── BLOG_POST.md               # Technical deep-dive writeup
└── README.md
```

---

## Quickstart

### 1. Installation

```bash
git clone https://github.com/anothercodingguy/hhgoa4.git
cd hhgoa4

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the 20 Benchmark Cases

Evaluates all 20 cases from `case_pack.csv` through the full investigation pipeline and writes JSON outputs to `cases/`:

```bash
python main.py --benchmark
```

### 3. Run Test Suite

Runs unit tests verifying graph algorithms, policy rules, and schema compliance for all 20 output JSON files:

```bash
pytest tests/ -v
```

### 4. Launch Analyst Workbench UI

Starts the local FastAPI server and opens the analyst investigation interface:

```bash
python main.py --serve --port 8000
```

Navigate to `http://127.0.0.1:8000` in your browser.

---

## Graph Architecture & Data Model

### Vertices
- `Customer`: Unique customer profile (`customer_id`, risk baseline).
- `Card`: Payment card token (`card_id`, network, card type).
- `Transaction`: Individual card transaction (`txn_id`, amount, timestamp, product code, risk score).
- `DeviceProfile`: Fingerprinted hardware & network profile (`device_id`, device info, OS, browser, proxy status).
- `BillingRegion`: Geographic billing cluster (`addr1`, `addr2`, country).
- `InvestigationCase`: Closed historical case or active alert (`case_id`, verdict, pattern, SAR status).

### Edges
- `HOLDS`: `Customer -> Card`
- `MADE`: `Card -> Transaction`
- `FROM_DEVICE`: `Transaction -> DeviceProfile`
- `BILLED_IN`: `Transaction -> BillingRegion`
- `NEXT_TXN`: `Transaction -> Transaction` (chronological sequence on same card)
- `TARGETS_CARD`: `InvestigationCase -> Card`
- `ASSOCIATED_WITH`: `InvestigationCase -> DeviceProfile`

---

## Key Fraud Patterns Detected

1. **Undocumented Fraud Rings (Device Sharing)**:
   Discovered via 3-hop traversal: `Transaction -> FROM_DEVICE -> DeviceProfile <- FROM_DEVICE - Transaction <- MADE - Card`.
   Detects instances where a single device profile (e.g. `Samsung SM-G935F` behind a proxy) operates dozens of cards belonging to different cardholders.

2. **Card Testing (Policy R5)**:
   A chronological sliding window traversal over `NEXT_TXN` identifying rapid low-value transactions (typically <$5.00) followed by a high-value extraction attempt within 30 minutes.

3. **Geographic Drift (Policy R4)**:
   Billing region anomalies where a card is used in a geographic zone with zero prior transaction history within 6 hours of local activity, without travel notification.

4. **Card-Not-Present (CNP) Velocity**:
   High-frequency e-commerce transactions on newly issued or previously dormant card tokens exceeding velocity thresholds.

---

## Policy & Approval Routing Framework

Enforces **Bank Fraud Policy v1.0** rules:
- **Rule R1**: Requires customer verification before card blocking when probability is below 0.70.
- **Rule R2**: Mandatory step-up authentication when device fingerprint is unrecognized.
- **Rule R3**: Immediate administrative block and supervisor notification on confirmed syndicates.
- **Rule R4**: Geographic mismatch triggers temporary verification hold.
- **Rule R5**: Card testing pattern triggers immediate merchant decline.
- **Rule R6**: SAR filing required when fraud exposure exceeds $5,000, or when coordinated ring activity is detected regardless of dollar amount.

### Approval Routing Matrix
| Action | Condition | Required Route |
|---|---|---|
| `MONITOR_ACCOUNT`, `REQUEST_VERIFICATION`, `STEP_UP_AUTH` | Standard pre-evidence | `auto` |
| `DECLINE_TRANSACTION`, `BLOCK_CARD` | Exposure <= $2,500 | `L1` (Team Lead) |
| `BLOCK_CARD` | Exposure > $2,500 | `L2` (Fraud Manager) |
| `BLOCK_ALL_CARDS`, `FILE_REPORT` | Multi-card syndicate or regulatory filing | `L2` (Fraud Manager) |

---

## 20 Benchmark Case Results Summary

| Case ID | Trigger | Flagged Txn | Card | Pattern Detected | Final Verdict | Exposure | SAR Filed | Final Action | Route |
|---|---|---|---|---|---|---|---|---|---|
| HHG-001 | risk_score (0.61) | 3514030 | C12382-K1 | none | uncertain | $0.00 | No | DECLINE_TRANSACTION | L1 |
| HHG-002 | risk_score (0.79) | 3478782 | C11891-K1 | CNP | uncertain | $292.36 | No | DECLINE_TRANSACTION | L1 |
| HHG-003 | customer_report | 3530164 | C08623-K2 | CNP | fraud | $49.00 | No | BLOCK_CARD | L1 |
| HHG-004 | customer_report | 3583227 | C08106-K1 | undocumented (Ring) | fraud | $128.33 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-005 | risk_score (0.54) | 3523199 | C02923-K1 | undocumented (Ring) | uncertain | $100.07 | No | DECLINE_TRANSACTION | L1 |
| HHG-006 | customer_report | 3476682 | C07297-K1 | undocumented (Ring) | fraud | $482.12 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-007 | risk_score (0.87) | 3514948 | C09933-K2 | none | uncertain | $0.00 | No | DECLINE_TRANSACTION | L1 |
| HHG-008 | customer_report | 3558054 | C13171-K2 | CNP | fraud | $55.68 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-009 | customer_report | 3581141 | C08299-K1 | CNP | fraud | $30.02 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-010 | risk_score (0.90) | 3506725 | C10434-K1 | undocumented (Ring) | fraud | $1,000.03 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-011 | customer_report | 3583368 | C11923-K2 | undocumented (Ring) | fraud | $131.30 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-012 | risk_score (0.55) | 3553342 | C05876-K2 | none | uncertain | $0.00 | No | DECLINE_TRANSACTION | L1 |
| HHG-013 | risk_score (0.76) | 3526826 | C07671-K2 | undocumented (Ring) | fraud | $35.66 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-014 | analyst_request | 3478561 | C13487-K1 | undocumented (Ring) | fraud | $74.96 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-015 | risk_score (0.77) | 3464869 | C03042-K1 | undocumented (Ring) | uncertain | $599.94 | No | DECLINE_TRANSACTION | L1 |
| HHG-016 | customer_report | 3534820 | C09988-K1 | undocumented (Ring) | fraud | $59.67 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-017 | risk_score (0.57) | 3450629 | C04570-K1 | undocumented (Ring) | uncertain | $100.09 | No | DECLINE_TRANSACTION | L1 |
| HHG-018 | customer_report | 3491361 | C02354-K2 | CNP | fraud | $39.08 | No | BLOCK_CARD | L1 |
| HHG-019 | risk_score (0.90) | 3503878 | C07987-K2 | undocumented (Ring) | fraud | $99.92 | Yes | BLOCK_CARD + FILE_REPORT | L1 / L2 |
| HHG-020 | risk_score (0.52) | 3509359 | C12265-K2 | undocumented (Ring) | uncertain | $125.08 | No | DECLINE_TRANSACTION | L1 |

---

## Deploying to TigerGraph Savanna Cloud

To run against a live TigerGraph instance:

1. Create a graph instance on [TigerGraph Savanna Cloud](https://savanna.tgcloud.io).
2. Execute the GSQL scripts in order:
   ```gsql
   @tigergraph/schema.gsql
   @tigergraph/load_data.gsql
   @tigergraph/queries.gsql
   ```
3. Configure environment variables:
   ```bash
   export TG_HOST="https://your-instance.i.tgcloud.io"
   export TG_USERNAME="tigergraph"
   export TG_PASSWORD="your-password"
   export TG_GRAPH="FraudGraph"
   ```
4. Run the benchmark:
   ```bash
   python main.py --benchmark
   ```

---

## License

MIT License. Built for Hacker House Goa 2026.
