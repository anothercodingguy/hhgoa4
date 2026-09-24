# Social Media Posts

### X (Twitter)
Built an automated fraud investigation pipeline for Hacker House Goa 2026 using @TigerGraphDB, MCP, and GraphRAG.

Instead of scoring transactions in isolation, it runs multi-hop GSQL queries across 590k IEEE-CIS transactions to detect shared-device fraud rings and card-testing bursts, evaluates uncertainty against bank policies, and outputs next-best actions with FinCEN SAR drafts.

Check out the writeup and 20 benchmark case evaluations:
https://github.com/anothercodingguy/hhgoa4

---

### LinkedIn
Fraud happens in networks, not isolated database rows.

For Hacker House Goa 2026 (Track 4: Agentic Fraud Investigation), we built an autonomous investigation engine on TigerGraph to process transaction alerts from the IEEE-CIS dataset (~590,000 transactions and 144,000 identity records).

Key components:
1. TigerGraph Graph Queries: 3-hop traversals connecting transactions, cards, and device profiles to surface multi-account fraud syndicates and card-testing sequences.
2. Model Context Protocol (MCP) Server: Standardized tool interface exposing graph lookups and historical case memory to the agent.
3. GraphRAG Policy Engine: Evaluates Bank Fraud Policy v1.0 rules under uncertainty, preventing premature card freezes on weak signals and routing escalations to L1/L2 approval tiers.
4. Regulatory Filing: Automatically compiles FinCEN-compliant Suspicious Activity Reports (Form 111) for qualifying syndicate cases.

Full technical writeup and benchmark results: https://github.com/anothercodingguy/hhgoa4
