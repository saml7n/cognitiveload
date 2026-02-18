import json
import os
from jsonschema import validate, ValidationError
from typing import Dict, Any

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schemas", "triage_card.schema.json")

def _load_schema() -> Dict[str, Any]:
    with open(SCHEMA_FILE, "r") as f:
        return json.load(f)

def validate_triage_card(card: Dict[str, Any]) -> bool:
    """
    Validates a triage card against the JSON schema.
    Returns True if valid, raises ValidationError if invalid.
    """
    schema = _load_schema()
    try:
        validate(instance=card, schema=schema)
        return True
    except ValidationError:
        return False
