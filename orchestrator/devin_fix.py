"""
Orchestrator entrypoint — Devin auto-fix workflow.

Triggered when a user ticks the "Attempt auto-fix with Devin" checkbox on a
triage comment.  Starts a Devin session to reproduce, fix, and PR the issue.
"""

import json
import logging
import os
import re
import sys
from typing import Any

from orchestrator.devin_client import DevinClient
from orchestrator.github_client import GitHubClient, DEFAULT_MARKER
from orchestrator.fix_prompt_builder import build_fix_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# Labels applied by the fix workflow.
LABEL_FIX_ATTEMPTED = "devin:fix-attempted"
LABEL_FIX_FAILED = "devin:fix-failed"

# Timeout for the fix session (longer than triage — fixes take more time).
FIX_SESSION_TIMEOUT = 1200  # 20 minutes


# ---------------------------------------------------------------------------
# Checkbox detection
# ---------------------------------------------------------------------------


def checkbox_was_ticked(old_body: str, new_body: str) -> bool:
    """Return True if the auto-fix checkbox changed from unchecked to checked.

    Looks for the transition:
      - [ ] Attempt auto-fix with Devin  →  - [x] Attempt auto-fix with Devin
    """
    unchecked = "- [ ] Attempt auto-fix with Devin"
    checked = "- [x] Attempt auto-fix with Devin"
    return unchecked in old_body and checked in new_body


# ---------------------------------------------------------------------------
# Triage card extraction (from comment body)
# ---------------------------------------------------------------------------


def extract_card_from_comment(body: str) -> dict[str, Any] | None:
    """Extract the triage card JSON embedded in an HTML comment.

    Looks for: <!-- devin-triage:v1\n{...json...}\n-->
    """
    pattern = r"<!--\s*devin-triage:v1\s*\n(.*?)\n\s*-->"
    match = re.search(pattern, body, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# PR detection (did Devin open one?)
# ---------------------------------------------------------------------------


def _find_fix_pr(gh: GitHubClient, repo: str, issue_number: int) -> str | None:
    """Check whether Devin opened a PR for this issue's fix branch.

    Returns the PR URL if found, else None.
    """
    branch_name = f"devin/fix-issue-{issue_number}"
    url = f"{gh.base_url}/repos/{repo}/pulls"
    resp = gh._session.get(
        url, params={"head": f"{repo.split('/')[0]}:{branch_name}", "state": "open"}
    )
    resp.raise_for_status()
    prs = resp.json()
    if prs:
        return prs[0].get("html_url", prs[0].get("url"))
    return None


# ---------------------------------------------------------------------------
# Comment update helpers
# ---------------------------------------------------------------------------


def _render_success_section(pr_url: str) -> str:
    return (
        "\n\n### ✅ Auto-fix attempted\n"
        f"Devin opened a PR with a proposed fix: **{pr_url}**\n\n"
        "Please review the PR, verify the reproduction test, and merge if satisfied."
    )


def _render_failure_section(session_data: dict[str, Any]) -> str:
    """Build a failure section with pointers from Devin's messages."""
    lines = [
        "\n\n### ❌ Auto-fix failed",
        "",
        "Devin attempted to fix this issue but was unable to complete the fix.",
        "",
    ]

    # Extract useful context from Devin's messages.
    messages = session_data.get("messages") or session_data.get("conversation") or []
    devin_msgs = [
        m.get("message", "")
        for m in messages
        if isinstance(m, dict) and m.get("type") in ("devin_message",)
    ]

    # Take the last few meaningful messages as pointers.
    pointers = [msg for msg in devin_msgs[-3:] if len(msg.strip()) > 20]
    if pointers:
        lines.append("**What Devin tried / where it got stuck:**")
        for p in pointers:
            # Truncate very long messages
            snippet = p[:500] + ("…" if len(p) > 500 else "")
            lines.append(f"> {snippet}")
            lines.append("")

    lines.append("**Suggested next steps for manual investigation:**")
    lines.append("- Review the affected files listed in the triage card above.")
    lines.append("- Try to reproduce the bug locally with the steps in the issue.")
    lines.append("- Check if Devin created a partial branch that may contain useful work.")
    lines.append("")

    return "\n".join(lines)


def _update_comment_with_result(
    gh: GitHubClient,
    repo: str,
    issue_number: int,
    comment_body: str,
    result_section: str,
) -> None:
    """Append the result section to the existing triage comment."""
    # Remove any previous fix result section (idempotent re-run).
    body = re.sub(
        r"\n\n### [✅❌] Auto-fix.*",
        "",
        comment_body,
        flags=re.DOTALL,
    )
    updated_body = body + result_section
    gh.upsert_comment(repo, issue_number, DEFAULT_MARKER, updated_body)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def attempt_fix(
    *,
    repo: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    comment_body: str,
    fix_timeout: int = FIX_SESSION_TIMEOUT,
) -> None:
    """End-to-end auto-fix flow for a triaged issue.

    1. Extract triage card from the comment.
    2. Build fix prompt.
    3. Start Devin session + poll to completion.
    4. Check whether Devin opened a PR.
    5. Update the triage comment with success/failure.
    6. Apply labels.
    """
    logger.info("Attempting auto-fix for %s#%d — %s", repo, issue_number, issue_title)

    # --- Clients ----------------------------------------------------------
    devin = DevinClient()
    gh = GitHubClient()

    # --- 1. Extract triage card -------------------------------------------
    card = extract_card_from_comment(comment_body)
    if card is None:
        logger.error("No triage card found in comment — aborting fix.")
        return

    # --- 2. Build prompt --------------------------------------------------
    prompt = build_fix_prompt(
        repo=repo,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body,
        triage_card=card,
    )
    logger.info("Fix prompt built (%d chars).", len(prompt))

    # --- 3. Devin session -------------------------------------------------
    session_id = devin.create_session(prompt)
    logger.info("Devin fix session started: %s", session_id)

    session_data = devin.poll_session(session_id, timeout=fix_timeout)
    status = session_data.get("status_enum", session_data.get("status"))
    logger.info("Devin fix session ended with status: %s", status)

    # Nudge if blocked (same pattern as triage).
    MAX_UNBLOCK_ATTEMPTS = 2
    unblock_count = 0
    while status == "blocked" and unblock_count < MAX_UNBLOCK_ATTEMPTS:
        unblock_count += 1
        logger.info(
            "Devin is blocked (attempt %d/%d). Sending nudge.",
            unblock_count,
            MAX_UNBLOCK_ATTEMPTS,
        )
        devin.send_message(
            session_id,
            (
                "Do not wait for my input. You are running in fully autonomous "
                "mode. Proceed with your best judgement. If you cannot fix the "
                "bug, explain what you tried and stop. Do NOT open a PR if the "
                "tests fail."
            ),
        )
        session_data = devin.poll_session(session_id, timeout=fix_timeout)
        status = session_data.get("status_enum", session_data.get("status"))
        logger.info("Devin fix session status after nudge: %s", status)

    # --- 4. Check for PR --------------------------------------------------
    pr_url = _find_fix_pr(gh, repo, issue_number)

    # --- 5. Update comment ------------------------------------------------
    if pr_url:
        logger.info("Devin opened PR: %s", pr_url)
        result_section = _render_success_section(pr_url)
        _update_comment_with_result(gh, repo, issue_number, comment_body, result_section)
        gh.add_labels(repo, issue_number, [LABEL_FIX_ATTEMPTED])
    else:
        logger.warning("No PR found — fix likely failed.")
        result_section = _render_failure_section(session_data)
        _update_comment_with_result(gh, repo, issue_number, comment_body, result_section)
        gh.add_labels(repo, issue_number, [LABEL_FIX_FAILED])

    logger.info("Auto-fix flow complete for %s#%d.", repo, issue_number)


# ---------------------------------------------------------------------------
# CLI / GitHub Actions entry
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse environment variables (set by the GitHub Actions workflow) and run."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    issue_number_str = os.environ.get("ISSUE_NUMBER", "")
    issue_title = os.environ.get("ISSUE_TITLE", "")
    issue_body = os.environ.get("ISSUE_BODY", "")
    comment_body = os.environ.get("COMMENT_BODY", "")

    if not repo or not issue_number_str:
        print(
            "Error: GITHUB_REPOSITORY and ISSUE_NUMBER must be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        issue_number = int(issue_number_str)
    except ValueError:
        print(
            f"Error: ISSUE_NUMBER must be an integer, got '{issue_number_str}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    attempt_fix(
        repo=repo,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body,
        comment_body=comment_body,
    )


if __name__ == "__main__":
    main()
