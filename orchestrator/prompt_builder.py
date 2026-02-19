"""
Prompt construction for Devin triage sessions.

Builds a structured prompt that instructs Devin to analyse a GitHub issue
and return a JSON triage card conforming to our schema.
"""

import json
import os

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schemas", "triage_card.schema.json")


def _load_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


def get_triage_schema() -> dict:
    """Return the triage card JSON Schema (for structured_output_schema param)."""
    return _load_schema()


def build_triage_prompt(
    *,
    repo: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    playbook_active: bool = False,
) -> str:
    """Return the prompt string sent to Devin for triage.

    When *playbook_active* is ``True`` the attached Devin playbook already
    contains the full procedure, so the prompt only supplies context
    (issue details + output schema reference).  This keeps the prompt
    compact and avoids duplicating the playbook instructions.

    When *playbook_active* is ``False`` the prompt includes the full
    inline procedure so the session is self-contained.
    """
    schema = _load_schema()

    # -- Context header (always present) -----------------------------------
    header = f"""\
You are triaging a GitHub issue for the repository **{repo}**.

## Issue #{issue_number}: {issue_title}

{issue_body}

---
"""

    # -- Compact prompt (playbook handles procedure) -----------------------
    if playbook_active:
        return (
            header
            + f"""\
## Context

IMPORTANT: You are running in **fully autonomous mode**. Do NOT ask for
clarification or confirmation. Do NOT pause and wait for human input.

The attached playbook describes the step-by-step procedure.
Return repo-relative paths (not absolute sandbox paths) in `affected_paths`.

Return **only** a single JSON object (no markdown fences, no commentary)
with these fields: `schema_version` (always `"v1"`), `classification`,
`confidence`, `summary`, `questions`, `affected_paths`,
`suggested_labels`, `suggested_priority`.
"""
        )

    # -- Full inline prompt (no playbook) ----------------------------------
    return (
        header
        + f"""\
## Your task

IMPORTANT: You are running in **fully autonomous mode**. Do NOT ask for
clarification or confirmation. Do NOT pause and wait for human input.
Complete the entire task and return the JSON result in a single pass.

1. Read the issue carefully.
2. Clone the repository (you have access via the Devin GitHub App) and
   investigate the codebase to understand which files are likely affected.
3. Decide whether this is a **bug**, **feature-request**, **question**, or
   **unclear**.
4. If the issue is unclear or missing key information, list up to 4 targeted
   clarifying questions in the `questions` array — but still return the
   full JSON card. Do NOT ask ME for clarification.
5. If the issue is clear, provide a concise summary, affected file paths,
   suggested labels, and a priority.

## Output format

Return **only** a single JSON object (no markdown fences, no commentary)
conforming to this schema:

```json
{json.dumps(schema, indent=2)}
```

Field notes:
- `schema_version`: always `"v1"`.
- `classification`: one of `bug`, `feature-request`, `question`, `unclear`.
- `confidence`: 0.0 – 1.0, your confidence in the classification.
- `summary`: ≤ 1000 chars, human-readable.
- `questions`: list of strings (empty if the issue is clear).
- `affected_paths`: repo-relative file paths or folder prefixes (e.g. `demo_app/services/foo.py`, **not** absolute sandbox paths).
- `suggested_labels`: GitHub labels to apply (e.g. `["bug", "priority-high"]`).
- `suggested_priority`: one of `low`, `medium`, `high`, `critical`.

Return the JSON object now.
"""
    )
