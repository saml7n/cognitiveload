import json
import os
import pytest
from orchestrator.validation import validate_triage_card

# Paths to test files
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
EXAMPLES_DIR = os.path.join(BASE_DIR, "schemas", "examples")

def test_validate_valid_card():
    valid_file = os.path.join(EXAMPLES_DIR, "valid_triage.json")
    with open(valid_file, "r") as f:
        card = json.load(f)
    assert validate_triage_card(card) is True

def test_validate_invalid_card():
    invalid_file = os.path.join(EXAMPLES_DIR, "invalid_triage.json")
    with open(invalid_file, "r") as f:
        card = json.load(f)
    assert validate_triage_card(card) is False

def test_missing_required_fields():
    invalid_card = {
        "schema_version": "v1",
        "summary": "This is a summary"
        # missing classification, confidence
    }
    assert validate_triage_card(invalid_card) is False

def test_edge_case_max_summary():
    valid_card = {
        "schema_version": "v1",
        "classification": "bug",
        "confidence": 1.0,
        "summary": "A" * 500  # maxLength is 500
    }
    assert validate_triage_card(valid_card) is True
    
    invalid_card = valid_card.copy()
    invalid_card["summary"] = "A" * 501
    assert validate_triage_card(invalid_card) is False
