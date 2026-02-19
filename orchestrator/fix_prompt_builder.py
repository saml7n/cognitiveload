"""
Prompt construction for Devin auto-fix sessions.

Builds a structured prompt that instructs Devin to reproduce a bug,
fix it, verify the fix, and open a PR — all autonomously.
"""

import json
from typing import Any


def build_fix_prompt(
    *,
    repo: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    triage_card: dict[str, Any],
) -> str:
    """Return the prompt string sent to Devin for an auto-fix attempt.

    The prompt instructs Devin to:
    1. Understand the bug from the issue + triage card.
    2. Write a reproduction test.
    3. Fix the code.
    4. Verify (repro test + full test suite).
    5. Create a branch + open a PR.
    """
    card_json = json.dumps(triage_card, indent=2)
    affected = "\n".join(f"- {p}" for p in triage_card.get("affected_paths", []))
    branch_name = f"devin/fix-issue-{issue_number}"

    return f"""\
You are fixing a bug in the repository **{repo}**.

## Issue #{issue_number}: {issue_title}

{issue_body}

## Triage Card (machine-generated context)

```json
{card_json}
```

Likely affected files:
{affected}

---

## Your task

IMPORTANT: You are running in **fully autonomous mode**. Do NOT ask for
clarification or confirmation. Do NOT pause and wait for human input.
Complete the entire task in a single pass.

Follow these steps in order:

### Step 1 — Understand the bug
Read the issue and triage card. Inspect the affected files in the repository
(you have access via the Devin GitHub App).

### Step 2 — Write a reproduction test
Create a test script or test case that **demonstrates the bug**. The test
should FAIL on the current code, proving the bug exists. Place it alongside
the existing tests (e.g., in a `test_fix_issue_{issue_number}.py` file or
within the existing test module).

### Step 3 — Fix the code
Make the minimal code change needed to fix the bug. Prefer the smallest,
most targeted fix — do not refactor unrelated code.

### Step 4 — Verify
Run the reproduction test — it should now PASS.
Then run the full test suite to ensure no regressions:
```
PYTHONPATH=. python -m pytest
```
If any tests fail, adjust your fix until all tests pass.

### Step 5 — Commit and open a PR
1. Create a branch named `{branch_name}`.
2. Commit your changes with a clear message referencing the issue:
   `fix: <concise description> (closes #{issue_number})`
3. Push the branch and open a Pull Request targeting `main` with:
   - Title: `fix: <concise description>`
   - Body that explains what the bug was, what you changed, and links to
     the issue with `Closes #{issue_number}`.

## Important constraints
- Do NOT modify files outside the scope of this bug.
- Do NOT close the issue directly — the PR will handle that.
- If you cannot reproduce or fix the bug, stop and explain what you tried
  and where you got stuck. Do NOT open a PR if the tests fail.
- Complete everything autonomously. Do not wait for human input at any point.
"""
