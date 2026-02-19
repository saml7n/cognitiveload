# Fix Playbook

You are autonomously fixing a bug in a GitHub repository. Follow these
steps **in order**. Do not skip any step.

## Step 1 — Understand the bug
Read the issue and the triage card provided in the prompt. Inspect the
affected files listed in the triage card.

## Step 2 — Write a reproduction test
Create a test that **demonstrates the bug** — it must FAIL on the
current code. Place it alongside existing tests (e.g.
`test_fix_issue_<N>.py` or in the existing test module).

## Step 3 — Fix the code
Make the **minimal** code change to fix the bug. Do not refactor
unrelated code. Prefer targeted, small diffs.

## Step 4 — Verify
1. Run the reproduction test — it must now PASS.
2. Run the full test suite (`PYTHONPATH=. python -m pytest`).
3. If anything fails, adjust until green.

## Step 5 — Commit and open a PR
1. Create a branch named `devin/fix-issue-<N>`.
2. Commit with message: `fix: <description> (closes #<N>)`.
3. Push and open a PR targeting `main`.
4. PR body must explain the bug, the fix, and link the issue.

## Constraints
- You are running in **fully autonomous mode**. Do NOT ask for human input.
- Do NOT modify files outside the scope of this bug.
- Do NOT open a PR if tests fail.
- Complete everything in a single pass.
