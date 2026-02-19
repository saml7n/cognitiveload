"""
Orchestrator entrypoint — Devin auto-fix workflow.

Triggered when a user ticks an "Attempt auto-fix for #N" checkbox on a
PR nudge comment.  Starts a Devin session to reproduce, fix, and PR the issue.
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
from orchestrator.playbook_ids import FIX_PLAYBOOK_ID
from orchestrator.pr_nudge import PR_NUDGE_MARKER, _normalize_affected_paths

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# Labels applied by the fix workflow (on the *issue*, not the PR).
LABEL_FIX_ATTEMPTED = "devin:fix-attempted"
LABEL_FIX_FAILED = "devin:fix-failed"

# Timeout for the fix session (longer than triage — fixes take more time).
FIX_SESSION_TIMEOUT = 1200  # 20 minutes

# Max ACU spend per fix session (cost guard-rail). 0 or unset = no limit.
FIX_MAX_ACU = int(os.environ.get("FIX_MAX_ACU", "10")) or None

# Regex to find ticked auto-fix checkboxes and extract issue numbers.
_CHECKBOX_TICKED_RE = re.compile(
    r"- \[x\] \*\*Attempt auto-fix for #(\d+)\*\* with Devin"
)


# ---------------------------------------------------------------------------
# Checkbox detection
# ---------------------------------------------------------------------------


def detect_ticked_issues(old_body: str, new_body: str) -> list[int]:
    """Return issue numbers whose auto-fix checkbox was newly ticked.

    Compares old_body vs new_body of the nudge comment to find checkboxes
    that changed from ``[ ]`` to ``[x]``.
    """
    previously_ticked = {int(m) for m in _CHECKBOX_TICKED_RE.findall(old_body)}
    now_ticked = {int(m) for m in _CHECKBOX_TICKED_RE.findall(new_body)}
    return sorted(now_ticked - previously_ticked)


# ---------------------------------------------------------------------------
# Triage card extraction (from the *issue's* triage comment)
# ---------------------------------------------------------------------------


def extract_card_from_comment(body: str) -> dict[str, Any] | None:
    """Extract the triage card JSON embedded in an HTML comment.

    Looks for: ``<!-- devin-triage:v1\\n{...json...}\\n-->``
    """
    pattern = r"<!--\s*devin-triage:v1\s*\n(.*?)\n\s*-->"
    match = re.search(pattern, body, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1).strip())
    except (json.JSONDecodeError, ValueError):
        return None


def fetch_triage_card(
    gh: GitHubClient, repo: str, issue_number: int
) -> dict[str, Any] | None:
    """Fetch the triage card from the bot comment on the given issue."""
    comments = gh.get_issue_comments(repo, issue_number)
    for c in comments:
        body = c.get("body", "")
        if DEFAULT_MARKER in body:
            return extract_card_from_comment(body)
    return None


# ---------------------------------------------------------------------------
# PR detection (did Devin open one?)
# ---------------------------------------------------------------------------
# The Devin v1 session response includes a `pull_request: { url }` field
# when Devin opens a PR.  We read that directly — no GitHub API search needed.


# ---------------------------------------------------------------------------
# Comment update helpers
# ---------------------------------------------------------------------------


def _render_success_section(issue_number: int, pr_url: str) -> str:
    return (
        f"\n\n### ✅ Auto-fix for #{issue_number}\n"
        f"Devin opened a PR with a proposed fix: **{pr_url}**\n\n"
        "Please review the PR, verify the reproduction test, and merge if satisfied."
    )


def _render_failure_section(issue_number: int, session_data: dict[str, Any]) -> str:
    """Build a failure section with pointers from Devin's messages."""
    lines = [
        f"\n\n### ❌ Auto-fix failed for #{issue_number}",
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
    lines.append("- Review the affected files listed in the triage card on the issue.")
    lines.append("- Try to reproduce the bug locally with the steps in the issue.")
    lines.append("- Check if Devin created a partial branch that may contain useful work.")
    lines.append("")

    return "\n".join(lines)


def _update_nudge_comment_with_result(
    gh: GitHubClient,
    repo: str,
    pr_number: int,
    comment_body: str,
    issue_number: int,
    result_section: str,
) -> None:
    """Append the result section to the existing nudge comment on the PR."""
    # Remove any previous fix result for THIS issue (idempotent re-run).
    pattern = rf"\n\n### [✅❌] Auto-fix[^\n]*for #{issue_number}.*?(?=\n\n### |$)"
    body = re.sub(pattern, "", comment_body, flags=re.DOTALL)
    updated_body = body + result_section
    gh.upsert_comment(repo, pr_number, PR_NUDGE_MARKER, updated_body)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def attempt_fix(
    *,
    repo: str,
    pr_number: int,
    issue_number: int,
    comment_body: str,
    fix_timeout: int = FIX_SESSION_TIMEOUT,
) -> None:
    """End-to-end auto-fix flow for a single issue, triggered from a PR nudge.

    1. Fetch triage card from the issue's triage comment.
    2. Fetch issue details from the GitHub API.
    3. Build fix prompt.
    4. Start Devin session + poll to completion.
    5. Check whether Devin opened a PR.
    6. Update the nudge comment on the PR with success/failure.
    7. Apply labels on the issue.
    """
    logger.info(
        "Attempting auto-fix for %s#%d (from PR #%d)",
        repo, issue_number, pr_number,
    )

    # --- Clients ----------------------------------------------------------
    devin = DevinClient()
    gh = GitHubClient()

    # --- 1. Fetch triage card from the issue ------------------------------
    card = fetch_triage_card(gh, repo, issue_number)
    if card is None:
        logger.error("No triage card found on issue #%d — aborting fix.", issue_number)
        return

    # --- 2. Fetch issue details -------------------------------------------
    issue_url = f"{gh.base_url}/repos/{repo}/issues/{issue_number}"
    resp = gh._session.get(issue_url)
    resp.raise_for_status()
    issue_data = resp.json()
    issue_title = issue_data.get("title", "")
    issue_body = issue_data.get("body", "")

    # Normalise affected paths in the card before building the prompt,
    # so Devin sees repo-relative paths even if the original triage
    # card contained absolute sandbox paths.
    if card.get("affected_paths"):
        card["affected_paths"] = _normalize_affected_paths(
            card["affected_paths"], repo
        )

    # --- 2. Build prompt --------------------------------------------------
    prompt = build_fix_prompt(
        repo=repo,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body,
        triage_card=card,
        playbook_active=True,
    )
    logger.info("Fix prompt built (%d chars).", len(prompt))

    # --- 3. Devin session -------------------------------------------------
    session_id = devin.create_session(
        prompt,
        title=f"Fix: Issue #{issue_number} \u2014 {issue_title[:60]}",
        tags=["fix", f"issue-{issue_number}", f"pr-{pr_number}"],
        idempotent=True,
        playbook_id=FIX_PLAYBOOK_ID,
        max_acu_limit=FIX_MAX_ACU,
    )
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

    # --- 4. Check for PR (native Devin session field) ---------------------
    pr_url = (session_data.get("pull_request") or {}).get("url")

    # --- 5. Update nudge comment on the PR --------------------------------
    if pr_url:
        logger.info("Devin opened PR: %s", pr_url)
        result_section = _render_success_section(issue_number, pr_url)
        _update_nudge_comment_with_result(
            gh, repo, pr_number, comment_body, issue_number, result_section,
        )
        gh.add_labels(repo, issue_number, [LABEL_FIX_ATTEMPTED])
    else:
        logger.warning("No PR found — fix likely failed.")
        result_section = _render_failure_section(issue_number, session_data)
        _update_nudge_comment_with_result(
            gh, repo, pr_number, comment_body, issue_number, result_section,
        )
        gh.add_labels(repo, issue_number, [LABEL_FIX_FAILED])

    logger.info("Auto-fix flow complete for issue #%d.", issue_number)


# ---------------------------------------------------------------------------
# CLI / GitHub Actions entry
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse environment variables (set by the GitHub Actions workflow) and run.

    The workflow passes:
    - GITHUB_REPOSITORY, PR_NUMBER
    - COMMENT_BODY  (current nudge comment body, after edit)
    - COMMENT_BODY_PREVIOUS  (nudge comment body before the edit)
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number_str = os.environ.get("PR_NUMBER", "")
    comment_body = os.environ.get("COMMENT_BODY", "")
    comment_body_previous = os.environ.get("COMMENT_BODY_PREVIOUS", "")

    if not repo or not pr_number_str:
        print(
            "Error: GITHUB_REPOSITORY and PR_NUMBER must be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        pr_number = int(pr_number_str)
    except ValueError:
        print(
            f"Error: PR_NUMBER must be an integer, got '{pr_number_str}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Detect which issue checkboxes were newly ticked.
    ticked_issues = detect_ticked_issues(comment_body_previous, comment_body)
    if not ticked_issues:
        logger.info("No new auto-fix checkboxes ticked — nothing to do.")
        return

    logger.info("Auto-fix requested for issue(s): %s", ticked_issues)

    for issue_number in ticked_issues:
        attempt_fix(
            repo=repo,
            pr_number=pr_number,
            issue_number=issue_number,
            comment_body=comment_body,
        )


if __name__ == "__main__":
    main()
