"""
Benchmark Case Schema and Specification Compliance Tests.
Validates all 20 benchmark case JSON answers against the exact IEEE-CIS Answer Format in README.md.
"""
import json
from pathlib import Path
import pytest
from src.config import settings

VALID_STATUSES = {"open", "closed_fraud", "closed_legitimate", "escalated"}
VALID_VERDICTS = {"fraud", "legitimate", "uncertain"}
VALID_PATTERNS = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none"
}
VALID_ROUTES = {"auto", "L1", "L2"}

@pytest.fixture
def case_files():
    files = sorted(list(settings.cases_dir.glob("HHG-*.json")))
    assert len(files) == 20, f"Expected exactly 20 case files, found {len(files)}"
    return files

def test_all_20_cases_present(case_files):
    for i in range(1, 21):
        expected_name = f"HHG-{i:03d}.json"
        assert (settings.cases_dir / expected_name).exists(), f"Missing {expected_name}"

def test_case_schema_and_integrity(case_files):
    for f in case_files:
        with open(f, "r", encoding="utf-8") as jf:
            data = json.load(jf)

        # Top level keys
        for key in ["case_id", "case", "evidence_requests", "next_best_actions", "sar", "stop_reason", "tool_calls", "tokens", "latency_s"]:
            assert key in data, f"Missing top-level key '{key}' in {f.name}"

        # Part 1: Case
        c = data["case"]
        assert c["status"] in VALID_STATUSES, f"Invalid status '{c['status']}' in {f.name}"
        assert c["verdict"] in VALID_VERDICTS, f"Invalid verdict '{c['verdict']}' in {f.name}"
        assert 0.0 <= c["fraud_probability"] <= 1.0, f"Probability out of range in {f.name}"
        assert c["pattern"] in VALID_PATTERNS, f"Invalid pattern '{c['pattern']}' in {f.name}"
        assert isinstance(c["affected_txn_ids"], list), f"affected_txn_ids must be list in {f.name}"
        assert isinstance(c["connected_card_ids"], list), f"connected_card_ids must be list in {f.name}"
        assert isinstance(c["connected_device_profiles"], list), f"connected_device_profiles must be list in {f.name}"
        assert isinstance(c["exposure_usd"], (int, float)) and c["exposure_usd"] >= 0.0
        assert isinstance(c["evidence"], list) and len(c["evidence"]) > 0, f"Empty evidence in {f.name}"
        assert isinstance(c["written_to_graph"], bool)
        assert c["written_to_graph"] is True, f"written_to_graph must be True in {f.name}"

        # If undocumented pattern, pattern_description must be present
        if c["pattern"] == "undocumented":
            assert len(c.get("pattern_description", "")) > 10, f"pattern_description missing for undocumented pattern in {f.name}"

        # Part 2: SAR
        sar = data["sar"]
        assert isinstance(sar["file"], bool)
        
        # Check agreement between FILE_REPORT in final actions and sar.file
        final_action_names = [a["action"] for a in data["next_best_actions"]["final"]]
        file_report_in_final = "FILE_REPORT" in final_action_names
        assert sar["file"] == file_report_in_final, f"SAR file flag ({sar['file']}) does not match FILE_REPORT in final actions ({file_report_in_final}) in {f.name}"

        if sar["file"]:
            assert len(sar["narrative"]) > 50, f"SAR narrative empty when file=true in {f.name}"
            assert len(sar["subjects"]) > 0, f"SAR subjects empty when file=true in {f.name}"
            assert sar["total_amount_usd"] > 0, f"SAR total_amount_usd must be > 0 when file=true in {f.name}"
            assert len(sar["activity_dates"]) == 2, f"SAR activity_dates must have 2 dates in {f.name}"
        else:
            assert sar["narrative"] == "", f"SAR narrative must be empty when file=false in {f.name}"
            assert sar["subjects"] == [], f"SAR subjects must be empty when file=false in {f.name}"
            assert sar["total_amount_usd"] == 0, f"SAR total_amount_usd must be 0 when file=false in {f.name}"
            assert sar["activity_dates"] == [], f"SAR activity_dates must be empty when file=false in {f.name}"

        # Part 3: Next Best Actions
        nba = data["next_best_actions"]
        assert len(nba["initial"]) > 0, f"Initial actions empty in {f.name}"
        assert len(nba["final"]) > 0, f"Final actions empty in {f.name}"
        for a in nba["initial"] + nba["final"]:
            assert a["route"] in VALID_ROUTES, f"Invalid route '{a['route']}' in {f.name}"
            assert len(a["reason"]) > 0, f"Action reason empty in {f.name}"

        assert isinstance(nba["what_changed"], str) and len(nba["what_changed"]) > 0
