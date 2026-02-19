# Story 8 — Devin API Deep Integration: Implementation Plan

This document breaks down every deliverable from Story 8 into exact lines of code affected, the change required, and how each change is tested (unit + QA).

---

## Table of Contents

1. [Deliverable 1: Extend `DevinClient.create_session()`](#deliverable-1-extend-devinclientcreate_session)
2. [Deliverable 2: Structured Output Schema (triage)](#deliverable-2-structured-output-schema-triage)
3. [Deliverable 3: Native PR Detection (fix)](#deliverable-3-native-pr-detection-fix)
4. [Deliverable 4: Session Titles](#deliverable-4-session-titles)
5. [Deliverable 5: Session Tags](#deliverable-5-session-tags)
6. [Deliverable 6: ACU Cost Limits](#deliverable-6-acu-cost-limits)
7. [Deliverable 7: Idempotent Fix Sessions](#deliverable-7-idempotent-fix-sessions)
8. [Deliverable 8: Playbook Manager](#deliverable-8-playbook-manager)
9. [Deliverable 9: Wire Playbooks into Triage + Fix](#deliverable-9-wire-playbooks-into-triage--fix)

---

## Deliverable 1: Extend `DevinClient.create_session()`

### What

The `create_session()` method already uses `**kwargs` pass-through, so new parameters flow to the API payload automatically. However, the method signature should explicitly document the new parameters for clarity and IDE support, and the docstring needs updating.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/devin_client.py` | L64-85 | Add explicit keyword args to signature: `structured_output_schema`, `tags`, `title`, `max_acu_limit`, `idempotent`, `playbook_id`. Update docstring. Keep `**kwargs` for forward-compat. |

### Detail

```
Current signature (L64):
    def create_session(self, prompt: str, snapshot_id: Optional[str] = None, **kwargs) -> str:

New signature:
    def create_session(
        self,
        prompt: str,
        snapshot_id: Optional[str] = None,
        *,
        structured_output_schema: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        title: Optional[str] = None,
        max_acu_limit: Optional[int] = None,
        idempotent: bool = False,
        playbook_id: Optional[str] = None,
        **kwargs,
    ) -> str:
```

Payload construction (L75-80) updated to conditionally include each param only when non-None (avoids sending nulls to the API):

```python
payload = {"prompt": prompt, **kwargs}
if snapshot_id:
    payload["snapshot_id"] = snapshot_id
if structured_output_schema is not None:
    payload["structured_output_schema"] = structured_output_schema
if tags is not None:
    payload["tags"] = tags
if title is not None:
    payload["title"] = title
if max_acu_limit is not None:
    payload["max_acu_limit"] = max_acu_limit
if idempotent:
    payload["idempotent"] = True
if playbook_id is not None:
    payload["playbook_id"] = playbook_id
```

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_create_session_passes_structured_output_schema` | `test_devin_client.py` | Mock `requests.post` → verify `json=` payload contains `structured_output_schema` key with the schema dict. |
| `test_create_session_passes_tags_and_title` | `test_devin_client.py` | Pass `tags=["triage"]` and `title="Triage: #2"` → verify both in payload. |
| `test_create_session_passes_max_acu_limit` | `test_devin_client.py` | Pass `max_acu_limit=5` → verify payload. |
| `test_create_session_passes_idempotent_flag` | `test_devin_client.py` | Pass `idempotent=True` → verify `"idempotent": True` in payload. |
| `test_create_session_passes_playbook_id` | `test_devin_client.py` | Pass `playbook_id="pb_123"` → verify payload. |
| `test_create_session_omits_none_params` | `test_devin_client.py` | Call with defaults → verify payload is just `{"prompt": "..."}` with no extra keys. |
| `test_create_session_existing_test_still_passes` | `test_devin_client.py` | Existing `test_create_session_success` (L14) must still pass unchanged. |

### QA

- Trigger triage workflow on a test issue → inspect Devin API request logs (session URL returned in workflow output) → confirm all parameters are visible on the Devin dashboard session detail page.

---

## Deliverable 2: Structured Output Schema (triage)

### What

Pass the triage card JSON Schema to `create_session()` so Devin validates output server-side and returns it in the `structured_output` field.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/prompt_builder.py` | L13-17 | `_load_schema()` already exists and is private. Export it or add a public `get_triage_schema()` function that `triage.py` can import. |
| `orchestrator/triage.py` | L163-167 | Where `devin.create_session(prompt)` is called. Add `structured_output_schema=schema` kwarg. |
| `orchestrator/triage.py` | L15 | Add import: `from orchestrator.prompt_builder import build_triage_prompt, get_triage_schema` |

### Detail

In `prompt_builder.py`, expose the schema loader:

```python
# L13-17 — rename or add public accessor
def get_triage_schema() -> dict:
    """Return the triage card JSON Schema (for structured_output_schema param)."""
    return _load_schema()
```

In `triage.py`, around L160-167:

```python
# Current:
session_id = devin.create_session(prompt)

# New:
from orchestrator.prompt_builder import get_triage_schema
schema = get_triage_schema()
session_id = devin.create_session(
    prompt,
    structured_output_schema=schema,
)
```

Note: `_extract_triage_card()` (L88-131) already checks `structured_output` first — no change needed there.

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_triage_passes_structured_output_schema` | `test_triage.py` | In `TestTriageIssue`: mock DevinClient, call `triage_issue()`, assert `devin.create_session` was called with `structured_output_schema=` matching the schema from `triage_card.schema.json`. |
| `test_extract_triage_card_from_structured_output` | `test_triage.py` | Already exists as `test_from_structured_output` (L52). Verify it still passes — confirms the extraction path works when API populates the field. |

### QA

- Trigger triage on a test issue → Devin session produces output in `structured_output` field → triage comment appears correctly.
- Verify in Devin dashboard that session shows "Structured Output Schema" configured.

---

## Deliverable 3: Native PR Detection (fix)

### What

Replace the `_find_fix_pr()` GitHub API branch search with reading `session_data["pull_request"]["url"]` from the Devin session response. Delete the old function entirely.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/devin_fix.py` | L89-103 | **Delete** the entire `_find_fix_pr()` function (15 lines). |
| `orchestrator/devin_fix.py` | L258 | Replace `pr_url = _find_fix_pr(gh, repo, issue_number)` with `pr_url = (session_data.get("pull_request") or {}).get("url")`. |
| `orchestrator/tests/test_devin_fix.py` | L211-218 | **Delete** `_mock_pr_response()` helper — no longer needed. |
| `orchestrator/tests/test_devin_fix.py` | L247-249 | In `test_success_flow`: remove `self._mock_pr_response(...)` from `gh._session.get.side_effect` list. Add `"pull_request": {"url": "https://github.com/owner/repo/pull/42"}` to `devin.poll_session.return_value`. |
| `orchestrator/tests/test_devin_fix.py` | L292-294 | In `test_failure_flow`: remove `self._mock_pr_response(None)` from side_effect. Ensure `poll_session.return_value` has no `pull_request` key (or `pull_request: None`). |

### Detail

The key change in `attempt_fix()` around L255-260:

```python
# Current (L258):
pr_url = _find_fix_pr(gh, repo, issue_number)

# New:
pr_url = (session_data.get("pull_request") or {}).get("url")
```

This also simplifies the `gh._session.get.side_effect` setup in tests — we go from 2 mock responses (issue fetch + PR search) to 1 (issue fetch only).

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_success_flow_reads_pr_from_session_data` | `test_devin_fix.py` | Replaces existing `test_success_flow_posts_pr_link_on_nudge`. `poll_session` returns `{"pull_request": {"url": "https://..."}}` → success section posted with that URL. `_find_fix_pr` is never called (function deleted). |
| `test_failure_flow_when_no_pr_in_session_data` | `test_devin_fix.py` | Replaces existing `test_failure_flow_posts_pointers_on_nudge`. `poll_session` returns `{}` (no `pull_request` key) → failure section posted. |
| `test_pr_url_none_when_pull_request_is_null` | `test_devin_fix.py` | New test. `poll_session` returns `{"pull_request": None}` → treated as failure (no PR). |

### QA

- Trigger auto-fix via checkbox → Devin opens PR → confirm `session_data["pull_request"]["url"]` is read correctly → success section on nudge comment shows the correct PR link.
- Trigger auto-fix on an unfixable bug → Devin finishes without PR → confirm failure flow fires correctly.

---

## Deliverable 4: Session Titles

### What

Both triage and fix sessions pass a human-readable `title` to `create_session()`.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/triage.py` | L163-167 | Add `title=f"Triage: Issue #{issue_number} — {issue_title[:60]}"` to `create_session()` call. |
| `orchestrator/devin_fix.py` | L237-240 | Add `title=f"Fix: Issue #{issue_number} — {issue_title[:60]}"` to `create_session()` call. |

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_triage_session_has_title` | `test_triage.py` | In `TestTriageIssue.test_clear_issue_gets_triaged_label`: assert `devin.create_session` was called with `title=` kwarg containing `"Triage:"` and the issue number. |
| `test_fix_session_has_title` | `test_devin_fix.py` | In `TestAttemptFix.test_success_flow`: assert `devin.create_session` was called with `title=` kwarg containing `"Fix:"` and the issue number. |

### QA

- Trigger both workflows → check Devin dashboard → sessions have descriptive titles instead of auto-generated ones.

---

## Deliverable 5: Session Tags

### What

Both triage and fix sessions pass `tags` for observability/filtering.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/triage.py` | L163-167 | Add `tags=["triage", f"issue-{issue_number}"]` to `create_session()` call. |
| `orchestrator/devin_fix.py` | L237-240 | Add `tags=["fix", f"issue-{issue_number}", f"pr-{pr_number}"]` to `create_session()` call. |

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_triage_session_has_tags` | `test_triage.py` | Assert `devin.create_session` called with `tags=["triage", "issue-2"]`. |
| `test_fix_session_has_tags` | `test_devin_fix.py` | Assert `devin.create_session` called with `tags=["fix", "issue-2", "pr-10"]`. |

### QA

- Trigger both workflows → check Devin dashboard → sessions can be filtered by tags.

---

## Deliverable 6: ACU Cost Limits

### What

Both triage and fix sessions pass `max_acu_limit` for cost control.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/triage.py` | L22 (new constant) | Add `TRIAGE_MAX_ACU = int(os.environ.get("TRIAGE_MAX_ACU", "5"))` |
| `orchestrator/triage.py` | L163-167 | Add `max_acu_limit=TRIAGE_MAX_ACU` to `create_session()` call. |
| `orchestrator/devin_fix.py` | L28 (new constant) | Add `FIX_MAX_ACU = int(os.environ.get("FIX_MAX_ACU", "10"))` |
| `orchestrator/devin_fix.py` | L237-240 | Add `max_acu_limit=FIX_MAX_ACU` to `create_session()` call. |

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_triage_session_has_acu_limit` | `test_triage.py` | Assert `devin.create_session` called with `max_acu_limit=5`. |
| `test_fix_session_has_acu_limit` | `test_devin_fix.py` | Assert `devin.create_session` called with `max_acu_limit=10`. |
| `test_acu_limit_configurable_via_env` | `test_triage.py` | Patch `os.environ` with `TRIAGE_MAX_ACU=20`, reload module, verify constant. |

### QA

- Trigger triage → check Devin dashboard → session shows ACU limit of 5.
- Trigger fix → session shows ACU limit of 10.

---

## Deliverable 7: Idempotent Fix Sessions

### What

Fix sessions pass `idempotent=True` to prevent duplicate sessions when a GitHub Actions workflow re-runs.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/devin_fix.py` | L237-240 | Add `idempotent=True` to `create_session()` call. |

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_fix_session_is_idempotent` | `test_devin_fix.py` | Assert `devin.create_session` called with `idempotent=True`. |

### QA

- Trigger auto-fix workflow → manually re-run the same workflow → confirm Devin returns the same session (not a duplicate). Check `is_new_session` field in the create response.

---

## Deliverable 8: Playbook Content + Upload Script + Workflow

### What

Playbook content lives in the repo as version-controlled markdown. A one-off
upload script and a manual-dispatch GitHub Actions workflow handle creation
and updates via the Devin API. No runtime API calls — playbook IDs are stored
as GitHub Actions secrets after uploading.

### Files

| File | Status | Purpose |
|---|---|---|
| `playbooks/triage.md` | **New** | Reusable triage instructions |
| `playbooks/fix.md` | **New** | Reusable auto-fix instructions |
| `scripts/upload_playbooks.py` | **New** | CLI to create/update playbooks via Devin API |
| `.github/workflows/upload-playbooks.yml` | **New** | Manual dispatch workflow to run the upload script |

### Usage

```bash
# Local one-off upload
DEVIN_API_KEY=apk_... python scripts/upload_playbooks.py

# Update existing playbooks
DEVIN_API_KEY=apk_... python scripts/upload_playbooks.py \
    --triage-id pb_abc123 --fix-id pb_def456

# Via GitHub Actions: Actions → "Upload Devin Playbooks" → Run workflow
# Optionally pass existing IDs to update instead of create.
```

Output: `TRIAGE_PLAYBOOK_ID=pb_...` and `FIX_PLAYBOOK_ID=pb_...` — store
these as GitHub Actions secrets.

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_create_playbook_returns_id` | `test_upload_playbooks.py` | Mock POST → returns playbook_id |
| `test_update_playbook_calls_put` | `test_upload_playbooks.py` | Mock PUT → URL contains playbook_id |
| `test_triage_playbook_exists` | `test_upload_playbooks.py` | `playbooks/triage.md` exists and is non-empty |
| `test_fix_playbook_exists` | `test_upload_playbooks.py` | `playbooks/fix.md` exists and is non-empty |

### QA

- Run workflow → Devin dashboard → Settings → Playbooks → confirm both exist.
- Re-run with IDs → confirm updated (not duplicated).

---

## Deliverable 9: Wire Playbooks into Triage + Fix

### What

`triage.py` and `devin_fix.py` read `TRIAGE_PLAYBOOK_ID` / `FIX_PLAYBOOK_ID`
from environment variables and pass `playbook_id` to `create_session()`.
No runtime API calls — the IDs are set once via secrets after running the
upload workflow.

### Files & lines affected

| File | Lines | Change |
|---|---|---|
| `orchestrator/triage.py` | Module-level | `TRIAGE_PLAYBOOK_ID = os.environ.get("TRIAGE_PLAYBOOK_ID")` |
| `orchestrator/triage.py` | `create_session()` call | Add `playbook_id=TRIAGE_PLAYBOOK_ID` |
| `orchestrator/devin_fix.py` | Module-level | `FIX_PLAYBOOK_ID = os.environ.get("FIX_PLAYBOOK_ID")` |
| `orchestrator/devin_fix.py` | `create_session()` call | Add `playbook_id=FIX_PLAYBOOK_ID` |
| `.github/workflows/issue-triage.yml` | env block | `TRIAGE_PLAYBOOK_ID: ${{ secrets.TRIAGE_PLAYBOOK_ID }}` |
| `.github/workflows/devin-fix.yml` | env block | `FIX_PLAYBOOK_ID: ${{ secrets.FIX_PLAYBOOK_ID }}` |

### Unit tests

| Test | File | What it asserts |
|---|---|---|
| `test_triage_session_has_playbook_id` | `test_triage.py` | Patch `TRIAGE_PLAYBOOK_ID` → assert `create_session` called with `playbook_id`. |
| `test_fix_session_has_playbook_id` | `test_devin_fix.py` | Patch `FIX_PLAYBOOK_ID` → assert `create_session` called with `playbook_id`. |

### QA

- Set `TRIAGE_PLAYBOOK_ID` secret → trigger triage → Devin dashboard shows session linked to playbook.
- Without the secret → session works fine (playbook_id=None is ignored by the API).

---

## Summary: Files Changed

| File | Status | Deliverables |
|---|---|---|
| `orchestrator/devin_client.py` | **Modified** | D1 |
| `orchestrator/prompt_builder.py` | **Modified** | D2 |
| `orchestrator/triage.py` | **Modified** | D2, D4, D5, D6, D9 |
| `orchestrator/devin_fix.py` | **Modified** | D3, D4, D5, D6, D7, D9 |
| `playbooks/triage.md` | **New** | D8 |
| `playbooks/fix.md` | **New** | D8 |
| `scripts/upload_playbooks.py` | **New** | D8 |
| `.github/workflows/upload-playbooks.yml` | **New** | D8 |
| `.github/workflows/issue-triage.yml` | **Modified** | D6, D9 |
| `.github/workflows/devin-fix.yml` | **Modified** | D6, D9 |
| `orchestrator/tests/test_devin_client.py` | **Modified** | D1 |
| `orchestrator/tests/test_triage.py` | **Modified** | D2, D4, D5, D6, D9 |
| `orchestrator/tests/test_devin_fix.py` | **Modified** | D3, D4, D5, D6, D7, D9 |
| `orchestrator/tests/test_upload_playbooks.py` | **New** | D8 |

### New tests: 23 | Deleted code: `_find_fix_pr()` + `_mock_pr_response()`

---

## Implementation Order (actual)

1. **D1** — Extend `create_session()` signature ✅ `63ccdd5`
2. **D3** — Native PR detection + delete `_find_fix_pr()` ✅ `10163a3`
3. **D2** — Structured output schema ✅ `3e03165`
4. **D4** — Session titles ✅ `ec565b4`
5. **D5** — Session tags ✅ `6accdb9`
6. **D7** — Idempotent fix sessions ✅ `6c9aa31`
7. **D8** — Playbook content + upload script + workflow ✅ `8dc9509`
8. **D9** — Wire playbook IDs into triage + fix ✅ `5549773`
9. **D6** — ACU cost limits ✅ `37e8f36`

Final test count: **115 tests passing** (up from 92 pre-Story 8).
