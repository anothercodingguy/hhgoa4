"""
Regulatory references and FinCEN SAR standards module.
Provides structure and templates conforming to FinCEN narrative guidelines (Who, What, When, Where, How, Why).
"""
from typing import Dict, List, Any

REGULATORY_GUIDANCE = {
    "FinCEN_SAR_Narrative": {
        "standard": "FinCEN Narrative Guidance & Sufficient SAR Narrative Standards",
        "requirements": [
            "Who: Identify all subjects (customer IDs, card IDs, merchant details, shared device profiles).",
            "What: Detail the unauthorized or suspicious financial transactions, individual amounts, and total exposure.",
            "When: Specify the date range (first and last dates of suspicious activity).",
            "Where: Identify billing regions, IP addresses/countries, and online vs in-person channels.",
            "How: Document the modus operandi (e.g. card testing, syndicated proxy ring, account takeover, out-of-region drift).",
            "Why: Articulate why the activity is deemed suspicious and non-accidental, referencing corroborating graph links."
        ],
        "target_length": "6 to 12 complete, professional sentences standing independently."
    },
    "FATF_Cyber_Fraud": {
        "standard": "FATF Illicit Financial Flows from Cyber-Enabled Fraud",
        "red_flags": [
            "Multiple payment instruments accessed via common digital fingerprints (device/browser/proxy).",
            "Rapid succession of low-value probing transactions preceding significant capital extraction.",
            "Geographic velocity anomalies exceeding physical transportation feasibility."
        ]
    },
    "FFIEC_BSA_AML": {
        "standard": "FFIEC Suspicious Activity Reporting & Red Flags Manual",
        "red_flags": [
            "Structuring transaction amounts immediately beneath customary reporting/authorization thresholds ($500 limit evasion).",
            "Discrepancy between cardholder verified residential geography and transaction initiation points."
        ]
    }
}
