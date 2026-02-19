#!/usr/bin/env python3
"""
One-off script to upload (or update) Devin playbooks from local markdown files.

Usage:
    # Create new playbooks
    DEVIN_API_KEY=apk_... python scripts/upload_playbooks.py

    # Update existing playbooks (pass their IDs)
    DEVIN_API_KEY=apk_... python scripts/upload_playbooks.py \
        --triage-id pb_abc123 --fix-id pb_def456

Outputs the playbook IDs to stdout — store them as GitHub Actions secrets
(TRIAGE_PLAYBOOK_ID / FIX_PLAYBOOK_ID) or in your .env file.
"""

import argparse
import os
import sys
from pathlib import Path

import requests

BASE_URL = "https://api.devin.ai/v1"
PLAYBOOKS_DIR = Path(__file__).resolve().parent.parent / "playbooks"

PLAYBOOKS = {
    "triage": {
        "file": PLAYBOOKS_DIR / "triage.md",
        "title": "Issue Triage",
    },
    "fix": {
        "file": PLAYBOOKS_DIR / "fix.md",
        "title": "Auto-Fix Bug",
    },
}


def _headers() -> dict:
    api_key = os.environ.get("DEVIN_API_KEY")
    if not api_key:
        print("ERROR: DEVIN_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def create_playbook(title: str, body: str) -> str:
    """POST /v1/playbooks — returns the new playbook_id."""
    resp = requests.post(
        f"{BASE_URL}/playbooks",
        headers=_headers(),
        json={"title": title, "body": body},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["playbook_id"]


def update_playbook(playbook_id: str, title: str, body: str) -> None:
    """PUT /v1/playbooks/{playbook_id} — updates an existing playbook."""
    resp = requests.put(
        f"{BASE_URL}/playbooks/{playbook_id}",
        headers=_headers(),
        json={"title": title, "body": body},
    )
    resp.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Devin playbooks")
    parser.add_argument("--triage-id", default=None, help="Existing triage playbook ID (to update)")
    parser.add_argument("--fix-id", default=None, help="Existing fix playbook ID (to update)")
    args = parser.parse_args()

    existing_ids = {
        "triage": args.triage_id,
        "fix": args.fix_id,
    }

    results = {}

    for name, cfg in PLAYBOOKS.items():
        body = cfg["file"].read_text()
        title = cfg["title"]
        pid = existing_ids.get(name)

        if pid:
            print(f"Updating {name} playbook ({pid})...", file=sys.stderr)
            update_playbook(pid, title, body)
            results[name] = pid
            print(f"  ✓ Updated: {pid}", file=sys.stderr)
        else:
            print(f"Creating {name} playbook...", file=sys.stderr)
            pid = create_playbook(title, body)
            results[name] = pid
            print(f"  ✓ Created: {pid}", file=sys.stderr)

    # Machine-readable output
    print()
    print("─── Playbook IDs (add to GitHub Actions secrets) ───")
    print(f"TRIAGE_PLAYBOOK_ID={results['triage']}")
    print(f"FIX_PLAYBOOK_ID={results['fix']}")


if __name__ == "__main__":
    main()
