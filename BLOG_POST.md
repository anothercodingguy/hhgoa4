# Building an Autonomous Fraud Investigation Pipeline with TigerGraph, MCP, and GraphRAG

**Author**: Suyash Singh  
**Event**: Hacker House Goa 2026 (Track #4 — Agentic Fraud Investigation & Next-Best Action)  
**Repository**: [github.com/anothercodingguy/hhgoa4](https://github.com/anothercodingguy/hhgoa4)

---

## 1. The Core Problem: Fraud Networks vs Isolated Rows

Card fraud detection at financial institutions has a fundamental blind spot: transactions are scored in isolation. An ML model or rules engine calculates an anomaly score for a single $75 transaction. If the cardholder has never made that transaction before, or if the merchant category is unusual, the risk score spikes. But is it actual fraud, or is the cardholder simply buying a gift while on vacation?

When risk signals are uncertain, fraud analysts must manually piece together the puzzle:
- Did this device appear on other accounts?
- Were there rapid micro-transactions beforehand testing whether the card works?
- What does the bank's fraud policy say regarding card-blocking thresholds?
- Does this meet FinCEN regulatory thresholds for Suspicious Activity Reporting (SAR)?

Doing this manually for thousands of alerts per day is slow, fragmented, and error-prone. By the time an analyst pulls logs from three different systems, the money is already gone.

For the Hacker House Goa 2026 challenge, we built an autonomous fraud investigation pipeline powered by **TigerGraph**, **Model Context Protocol (MCP)**, and **GraphRAG**. Tested on the IEEE-CIS dataset (590k+ transactions, 144k+ identity records, and 5,565 closed historical cases), the system automates graph traversals, policy reasoning under uncertainty, next-best action execution, and regulatory filing.

---

## 2. Graph Schema & GSQL Traversal Design

Relational databases fall apart when evaluating fraud rings because finding shared infrastructure requires expensive multi-hop self-joins across millions of rows. In TigerGraph, we modeled the payment network as a native property graph:

```
[Customer] ──(HOLDS)──► [Card] ──(MADE)──► [Transaction] ──(FROM_DEVICE)──► [DeviceProfile]
                                   │
                               (BILLED_IN)
                                   ▼
                            [BillingRegion]
```

### Uncovering Shared-Device Fraud Rings

The most damaging fraud pattern in our dataset is the multi-account syndicate. Individual transactions look small and unremarkable, but multiple cards trace back to the same hardware fingerprint or proxy profile.

In GSQL, we traverse 3 hops to extract all cards connected to a suspect transaction's device:

```gsql
CREATE QUERY detect_device_sharing(VERTEX<Transaction> target_txn) FOR GRAPH FraudGraph {
    OrFilter = {};
    
    // Hop 1: Transaction -> DeviceProfile
    Devices = SELECT d FROM target_txn:t -(FROM_DEVICE:e)-> DeviceProfile:d;
    
    // Hop 2 & 3: DeviceProfile -> Transactions -> Cards
    SharedCards = SELECT c FROM Devices:d -(<FROM_DEVICE:e1)- Transaction:t -(<MADE:e2)- Card:c
                  ACCUM @@connected_card_count += 1;
                  
    PRINT @@connected_card_count, SharedCards;
}
```

On our dataset, this query revealed single device profiles (such as `Samsung SM-G935F` routing through anonymous proxies) controlling dozens of compromised cards across unrelated customer accounts. While a single transaction was only $74.96, the aggregated exposure across the ring exceeded thousands of dollars.

### Card Testing Sequences (Policy R5)

Card testing occurs when bad actors test stolen credentials with rapid, sub-$5 micro-transactions before attempting a major extraction. Using a chronological sliding window over `Transaction - (NEXT_TXN) -> Transaction` edges, our engine flags any card exhibiting 3+ rapid small transactions followed by a larger spike within 30 minutes.

---

## 3. The MCP Integration Layer

Rather than giving an LLM raw SQL access or unconstrained API keys, we used the **Model Context Protocol (MCP)** to expose standardized, read-only graph investigation tools:

- `get_card_history`: Retrieves chronological transaction velocity and volume baselines.
- `get_device_neighbors`: Traverses 3 hops to discover all cards and transactions sharing hardware/network profiles.
- `get_geographic_profile`: Compares transaction billing regions against the customer's 90-day baseline.
- `find_similar_cases`: Queries the 5,565 closed historical cases for pattern matches and prior outcomes.
- `lookup_policy_rule`: Fetches strict Bank Fraud Policy v1.0 specifications and required approval routes.

By structuring graph operations into typed MCP tools, the agent reliably gathers ground-truth evidence before generating claims.

---

## 4. Reasoning Under Uncertainty & Next-Best Action

A core requirement of the HHGOA challenge is navigating uncertainty without overreacting. Under **Bank Fraud Policy v1.0 (Rule R1)**, the agent is strictly prohibited from freezing a customer's card on weak signals (probability < 0.70) without prior customer outreach.

Our agent implements a two-stage decision lifecycle:

### Stage 1: Initial Next-Best Action (Pre-Evidence)
When an alert arrives, the agent assesses the raw model score against graph indicators. If the evidence is inconclusive (e.g. out-of-region swipe with clean device history):
- Recommended action: `REQUEST_VERIFICATION` or `STEP_UP_AUTH`.
- Approval route: `auto`.
- A temporary hold or monitoring flag is placed while the cardholder is contacted.

### Stage 2: Controlled Evidence & Final Action
The agent simulates or receives customer validation (e.g. cardholder denies transaction vs confirms legitimate travel). Upon receiving evidence:
- If denied: Calibrated probability jumps to 0.98. Final action shifts to `BLOCK_CARD` with approval routed to `L1` (Team Lead) for exposure <= $2,500, or `L2` (Fraud Manager) for exposure > $2,500.
- If ring activity is present: Action escalates to `BLOCK_ALL_CARDS` and `FILE_REPORT` routed to `L2`.
- The agent explicitly documents the **delta** between initial and final recommendations (`what_changed`), providing a clear audit trail.

---

## 5. Automated FinCEN SAR Generation (Form 111)

Under federal AML/CFT regulations, banks must file Suspicious Activity Reports (SARs) when suspicious activity involves known syndicate networks or exceeds statutory dollar thresholds ($5,000 for standard transactions, or any amount for coordinated ring operations).

For qualifying cases, our pipeline automatically drafts a 6-12 sentence regulatory narrative covering all FinCEN requirements:
- **Who**: Suspect identifiers, device fingerprints, associated customer profiles.
- **What**: Financial instrument, card tokens, total exposure amount.
- **When & Where**: Timestamps, IP locations, billing regions.
- **How & Why**: Modus operandi, graph traversal evidence, cited policy violations.

---

## 6. Key Learnings & Takeaways

1. **Raw Risk Scores are Inadequate**: A score of 0.85 can easily be a false positive caused by a new device or travel. Conversely, organized rings deliberately keep individual transaction amounts low to keep scores beneath 0.60. Graph traversal provides the missing context.
2. **Deterministic Fallbacks Enable Reproducibility**: While we engineered full GSQL scripts for TigerGraph Savanna Cloud, having an integrated in-memory graph emulator with identical schema guarantees that evaluators can verify all 20 benchmark cases locally with zero cloud configuration.
3. **Structured Policy Gates Prevent Hallucination**: Enforcing hard policy rules (R1-R10) and approval routes (Auto, L1, L2) through deterministic code rather than pure prompt instructions ensures strict compliance in regulated environments.

---

*Code and benchmark answers are available at [github.com/anothercodingguy/hhgoa4](https://github.com/anothercodingguy/hhgoa4).*
