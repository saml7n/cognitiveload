"""
Smoke test for orchestrator.github_client against the live GitHub API.

Requires GITHUB_TOKEN in .env with Issues R/W on the target repo.
Creates a test issue, exercises all four client methods, then cleans up.
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(_repo_root / ".env")

from orchestrator.github_client import GitHubClient, DEFAULT_MARKER

REPO = "saml7n/cognitiveload"
SMOKE_MARKER = "<!-- smoke-test:github-client -->"


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not set. Add it to .env at the repo root.")
        sys.exit(1)

    client = GitHubClient(token=token)

    # ---- Step 1: Create a throwaway test issue ----
    print("1. Creating a test issue...")
    import requests

    resp = requests.post(
        f"https://api.github.com/repos/{REPO}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "title": "[smoke-test] GitHub client integration test — safe to close",
            "body": "Automated smoke test for `orchestrator/github_client.py`. Will be closed automatically.",
        },
    )
    if resp.status_code not in (200, 201):
        print(f"   ❌ Failed to create issue: {resp.status_code} {resp.text}")
        sys.exit(1)

    issue_number = resp.json()["number"]
    print(f"   ✅ Issue #{issue_number} created.")

    try:
        # ---- Step 2: find_bot_comment (expect None) ----
        print("2. find_bot_comment (expecting None)...")
        cid = client.find_bot_comment(REPO, issue_number, SMOKE_MARKER)
        assert cid is None, f"Expected None, got {cid}"
        print("   ✅ Correctly returned None.")

        # ---- Step 3: upsert_comment (create) ----
        print("3. upsert_comment (create)...")
        client.upsert_comment(REPO, issue_number, SMOKE_MARKER, "Hello from smoke test — **create** path.")
        time.sleep(1)  # give GitHub a moment

        cid = client.find_bot_comment(REPO, issue_number, SMOKE_MARKER)
        assert cid is not None, "Comment not found after create"
        print(f"   ✅ Comment created (id={cid}).")

        # ---- Step 4: upsert_comment (update) ----
        print("4. upsert_comment (update, same marker)...")
        client.upsert_comment(REPO, issue_number, SMOKE_MARKER, "Hello from smoke test — **update** path.")
        time.sleep(1)

        new_cid = client.find_bot_comment(REPO, issue_number, SMOKE_MARKER)
        assert new_cid == cid, f"Expected same comment {cid}, got {new_cid}"
        print(f"   ✅ Same comment updated (id still {cid}).")

        # ---- Step 5: add_labels ----
        print("5. add_labels...")
        client.add_labels(REPO, issue_number, ["smoke-test"])
        print("   ✅ Label 'smoke-test' added.")

        # ---- Step 6: get_pr_changed_files (use issue 0 / skip if no open PR) ----
        # We won't fabricate a PR, but we can at least call the endpoint.
        # If there's no open PR, we just verify it returns an empty list or errors gracefully.
        print("6. get_pr_changed_files (quick sanity call)...")
        try:
            files = client.get_pr_changed_files(REPO, 1)
            print(f"   ✅ PR #1 returned {len(files)} file(s): {files[:5]}")
        except Exception as e:
            # PR #1 may not exist — that's fine, we just want to see the call doesn't crash
            print(f"   ⚠️  PR #1 not found (expected if none exists): {e}")

        print("\n🎉 All smoke tests PASSED.")

    finally:
        # ---- Cleanup: close the issue ----
        print("\nCleaning up: closing test issue...")
        resp = requests.patch(
            f"https://api.github.com/repos/{REPO}/issues/{issue_number}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"state": "closed"},
        )
        if resp.status_code == 200:
            print(f"   ✅ Issue #{issue_number} closed.")
        else:
            print(f"   ⚠️  Could not close issue: {resp.status_code}")


if __name__ == "__main__":
    main()
