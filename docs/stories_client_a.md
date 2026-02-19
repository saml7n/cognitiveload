# User Stories: Client A (FinServ Co) — Issue Intelligence + PR-Time Nudges

Stories are ordered by dependency. Each one produces a concrete, testable output that the next story builds on.

**Rules:**
- No work begins on a story until every item in "Blocked until answered" is answered and recorded in this file.
- One commit per story.
- Each story must pass its verification step before moving to the next.

**Dependency chain:**
```
Story 0: Decisions (no code)
  → Story 1: Demo monorepo (the thing the bot will triage)
    → Story 2: Triage card contract (schema + template — design artifacts only)
      → Story 3: Devin API client (standalone, tested in isolation)
      → Story 4: GitHub API helpers (standalone, tested in isolation)
        → Story 5: Issue intake workflow (first time the "bot" runs end-to-end)
          → Story 6: PR-time nudge workflow (uses triage card data from Story 5)
            → Story 7: Devin auto-fix workflow (checkbox-triggered, Devin does the heavy lifting)
              → Story 8: Devin API deep integration (structured output, playbooks, observability)
```

---

## Story 0 — Decide the operating model

As a **VP Engineering at FinServ Co**, I want **clear rules for what this automation does and doesn't do**, so that **I can trust it near production code without babysitting it**.

### Acceptance criteria
- [x] The following decisions are recorded in this file (below):
  - How triage is triggered (label, slash command, or automatic on issue open).
  - The exact label names used by the system and what each one means.
  - Whether the bot can create PRs or only comment and label.
  - Whether the bot can close issues or only add information.
  - Rate limits (max issues processed per workflow run).
  - Idempotency rule (one bot comment per issue, updated on rerun).
- [x] The demo scope is written down:
  - In scope: issue clarification/triage + PR-time nudges.
  - Stretch: fix-mode PRs.

### Verification
- Read through the recorded answers below. If any are blank, the story is not done.

### Blocked until answered
1. Trigger policy: label-only, slash-command-only, or automatic on issue open?
2. Should the bot ever create PRs in this PoC, or comment/label only?
3. Demo target: this repo (`cognitiveload`), or a separate repo?
4. Can we add GitHub Actions workflows to the repo and run them on your GitHub account?
5. Can the bot close or reassign issues, or is it strictly additive (comment + label)?

**Recorded answers:**
- Trigger policy: Automatic on all new issues; label-based (`devin:triage`) for backlog.
- PR creation scope: Comment and label only (PRs only in Story 8/Fix Mode).
- Demo target repo: This repo (`cognitiveload`).
- Actions permission: Yes, permitted to add workflows.
- Close/reassign allowed: Yes, permitted.

---

## Story 1 — Build the demo monorepo

As a **demo presenter**, I want **a small but realistic app with known bugs and a passing test suite**, so that **the triage bot has something meaningful to investigate and the demo is believable**.

### Acceptance criteria
- [x] A `demo_app/` directory exists containing a small working application (e.g., a Python Flask/FastAPI API or a Node Express app — language TBD).
- [x] The app has a test suite that passes when run (`pytest` or `npm test`).
- [x] There are 3 intentional bugs seeded in the code, each documented in `demo_app/BUGS.md`:
  - Bug A: a clear, well-described bug with an obvious fix (e.g., off-by-one in a calculation endpoint).
  - Bug B: a vague bug — the symptoms are described but the root cause requires investigation.
  - Bug C: a bug that is hard to reproduce without specific environment/input conditions.
- [x] Each bug entry in `BUGS.md` records:
  - the affected file path(s)
  - a one-line description
  - whether it's "clear," "vague," or "hard to repro"
- [x] The app can be installed and tested locally with a single command documented in `demo_app/README.md`.

### Verification
- Run the test suite: it passes.
- Confirm each documented bug is real (introduce the fix, see the relevant behavior change).

### Blocked until answered
1. Language/framework preference for the demo app (Python or Node recommended for speed).
2. Should the demo app live in this repo or a separate repo?

**Recorded answers:**
- Language/framework: Python (FastAPI)
- Repo location: This repo (`demo_app/`)

---

## Story 2 — Define the triage card contract

As a **junior engineer on triage rotation**, I want **a consistent, scannable format for every triaged issue**, so that **I can understand any issue in 30 seconds without reading the full thread**.

This story produces design artifacts only — no running bot, no workflows.

### Acceptance criteria
- [x] A JSON schema file exists at `orchestrator/schemas/triage_card.schema.json` defining the triage card structure with at minimum:
  - `schema_version` (string)
  - `classification` (enum: bug / feature-request / question / unclear)
  - `confidence` (number 0–1)
  - `summary` (string, ≤ 3 sentences)
  - `questions` (array of 0–4 strings — targeted clarification questions)
  - `affected_paths` (array of strings — file/folder paths in the repo)
  - `suggested_labels` (array of strings)
  - `suggested_priority` (enum: low / medium / high / critical)
- [x] A sample valid triage card JSON exists at `orchestrator/schemas/examples/valid_triage.json`.
- [x] A sample invalid triage card JSON exists at `orchestrator/schemas/examples/invalid_triage.json`.
- [x] A bot comment template exists at `orchestrator/templates/triage_comment.md` showing what the GitHub comment will look like, including:
  - a human-readable summary section
  - a stable HTML comment marker (e.g., `<!-- devin-triage:v1 -->`) for idempotent updates
  - the embedded JSON block
- [x] A Python validation function exists at `orchestrator/validation.py` that takes a dict and returns True/False against the schema.
- [x] Unit tests exist for the validation function (1 valid case, 1 invalid case, 1 edge case).

### Verification
- `pytest orchestrator/tests/test_validation.py` passes.

### Blocked until answered
1. "Affected paths" format: folder prefixes (e.g., `src/auth/`), file globs (e.g., `src/auth/*.py`), or exact file paths?
2. Should the comment be edited-in-place on rerun (recommended) or append a new comment?
3. Do you want "effort estimate" as a field, or keep it simple (classification + priority + paths)?

**Recorded answers:**
- Affected paths format: Exact file paths or folder prefixes (best for matching).
- Comment update behavior: Edit-in-place (recommended for idempotency).
- Effort estimate field: Keep it simple (PoC only).

---

## Story 3 — Devin API client (standalone)

As an **automation developer**, I want **a reliable, tested wrapper around the Devin API**, so that **I can start sessions and get results without worrying about polling logic or error handling every time**.

This story produces a standalone Python module — no GitHub integration yet.

### Acceptance criteria
- [x] A Python module exists at `orchestrator/devin_client.py` with:
  - `create_session(prompt: str, **kwargs) -> str` — returns session ID.
  - `poll_session(session_id: str, timeout: int, interval: int) -> dict` — polls with exponential backoff, returns final session state.
  - `send_message(session_id: str, message: str) -> None` — sends a follow-up message to a running session.
- [x] Polling handles all terminal states: `finished`, `stopped`, `blocked`.
  - On `blocked`: returns the state (does not hang).
  - On timeout: raises a clear exception.
- [x] The client reads the API key from environment variable `DEVIN_API_KEY`.
- [x] Unit tests exist using mocked HTTP responses (no real API calls in tests) covering:
  - successful session (working → finished)
  - session that goes blocked
  - session that times out
  - invalid API key (401)

### Verification
- `pytest orchestrator/tests/test_devin_client.py` passes.
- Optionally: a manual smoke test script that starts a real session with a trivial prompt and prints the result.

### Blocked until answered
1. Confirm the GitHub Actions secret name for the Devin API key (recommended: `DEVIN_API_KEY`).
2. Prompt-only for PoC, or also use snapshots/playbooks?
3. Rely on Devin's GitHub repo connection, or always instruct `git clone` explicitly in prompts?

**Recorded answers:**
- Secret name: `DEVIN_API_KEY`
- Execution mode: Pure prompts with `structured_output_schema`.
- Repo access method: Rely on Devin's GitHub connection (but can fall back to clone if needed).

---

## Story 4 — GitHub API helpers (standalone)

As an **automation developer**, I want **tested helpers for posting idempotent comments and applying labels via the GitHub API**, so that **the bot never spams and I can reuse these helpers across issue and PR workflows**.

This story produces a standalone Python module — no workflows yet.

### Acceptance criteria
- [x] A Python module exists at `orchestrator/github_client.py` with:
  - `find_bot_comment(repo, issue_number, marker) -> comment_id | None` — searches issue/PR comments for the stable marker.
  - `upsert_comment(repo, issue_number, marker, body) -> None` — creates or updates the bot's comment.
  - `add_labels(repo, issue_number, labels: list[str]) -> None` — adds labels without removing existing ones.
  - `get_pr_changed_files(repo, pr_number) -> list[str]` — returns list of changed file paths.
- [x] The module uses `GITHUB_TOKEN` from the environment.
- [x] Unit tests exist using mocked HTTP responses covering:
  - upsert when no prior comment exists (creates)
  - upsert when prior comment exists (updates)
  - add_labels adds without removing
  - get_pr_changed_files returns correct paths

### Verification
- `pytest orchestrator/tests/test_github_client.py` passes.

### Blocked until answered
1. Can the bot remove labels, or add-only?
2. Confirm marker format (recommended: `<!-- devin-triage:v1 -->`).

**Recorded answers:**
- Label removal: Add-only (safer for PoC).
- Marker format: `<!-- devin-triage:v1 -->`

---

## Story 5 — Issue intake workflow (first end-to-end "bot")

As an **engineer filing an issue**, I want the system to **ask targeted clarifying questions or provide a triage summary**, so that **my issue becomes actionable quickly without a long back-and-forth**.

This is the first story where all the pieces come together into a running GitHub Action.

### Acceptance criteria
- [x] A GitHub Actions workflow exists at `.github/workflows/issue-triage.yml` that triggers on the agreed event (from Story 0 decisions).
- [x] When triggered, the workflow:
  1. Calls the orchestrator entrypoint with the issue payload.
  2. The orchestrator starts a Devin session with a triage prompt.
  3. Devin's output is validated against the triage card schema (Story 2).
  4. The orchestrator posts/updates exactly one comment on the issue using the bot marker (Story 4).
  5. The orchestrator applies suggested labels (Story 4).
- [x] If the issue is unclear, the comment contains targeted questions and the label `needs-info` is applied.
- [x] If the issue is clear, the comment contains a full triage card and the label `devin:triaged` is applied.
- [x] Rerunning the workflow on the same issue updates the existing comment (no new comment created).
- [x] The workflow does not close issues, push code, or create PRs.

### Verification
- Open a test issue in the demo repo → workflow runs → triage comment appears.
- Rerun → same comment is updated, not duplicated.
- Open a vague issue → `needs-info` label + questions appear.

### Blocked until answered
1. Confirm the opt-in trigger mechanism (from Story 0 answers).
2. Confirm the Devin API key is added as a GitHub Actions secret.
3. Confirm the required labels exist in the repo.

**Recorded answers:**
- Trigger mechanism confirmed: Both — `issues: [opened]` for auto-triage + `issues: [labeled]` with `devin:triage` for backlog.
- API key secret added: User to add `DEVIN_API_KEY` as a GitHub Actions secret. `GITHUB_TOKEN` provided automatically.
- Labels created: `devin:triaged`, `needs-info`, `devin:triage` — all created in the repo.

---

## Story 6 — PR-time nudge workflow

As a **developer opening a PR**, I want to **see a heads-up when my changes touch code linked to a known issue**, so that **I can fix it while I'm already in that context instead of discovering it later**.

### Acceptance criteria
- [x] A GitHub Actions workflow exists at `.github/workflows/pr-nudge.yml` triggered on `pull_request` (opened + synchronize).
- [x] When triggered, the workflow:
  1. Fetches the list of files changed in the PR.
  2. Queries open issues with the `devin:triaged` label.
  3. Parses the embedded triage JSON from each issue's bot comment.
  4. Matches PR changed files against each issue's `affected_paths`.
  5. If matches found: posts/updates a single PR comment listing matched issues, why they matched, and a suggested next step.
- [x] If no matches are found, the bot is silent (no comment posted).
- [x] Reruns update the existing PR comment (no duplicates).

### Verification
- Open a PR that touches files matching a triaged issue's affected paths → nudge comment appears.
- Open a PR that touches unrelated files → no comment.
- Push new commits to an existing PR → comment is updated, not duplicated.

### Blocked until answered
1. Which label(s) qualify issues for nudges (`devin:triaged` only, or others)?
2. Max matches to show before truncating (e.g., top 5)?
3. Should the PR comment include a decision prompt (checkbox: fix now / defer) or be informational only?

**Recorded answers:**
- Nudge label(s): `devin:triaged` only — only issues with validated triage cards.
- Match cap: Top 5 matches; show "…and N more" if exceeded.
- PR comment style: Informational + per-issue auto-fix checkbox for qualifying bugs (Story 7).

---

## Story 7 — Devin auto-fix workflow (checkbox-triggered from PR nudge)

As a **developer reviewing a PR nudge**, I want to **tick a checkbox next to a matched issue and have Devin attempt to reproduce, fix, and commit a solution**, so that **I can get a bug fixed while I'm already working in that area of the code**.

This is where we let Devin do the heavy lifting — including its native GitHub integration for branching, committing, and opening PRs.

### Design

The PR nudge comment (Story 6) lists triaged issues whose `affected_paths` overlap with the PR's changed files. This story adds a conditional "attempt auto-fix" checkbox **per issue** in that nudge comment:

```markdown
### #42: Off-by-one in /summary endpoint
…issue details…
- [ ] **Attempt auto-fix for #42** with Devin
```

The checkbox is **only shown** next to issues that are actionable (`is_fixable`):
- Classification is `bug` (not `unclear`, `question`, or `feature-request`).
- The `questions` array is empty (no outstanding clarification needed).
- Confidence is ≥ 0.7.

Issues in the nudge that don't meet these criteria are still listed (they're still relevant context), but without the checkbox — the developer would need to investigate those manually.

**Why the PR nudge and not the triage comment?** The triage comment is purely informational — it lands when the issue is filed and nobody may be looking at it. The PR nudge appears when a developer is _already working on related code_, which is exactly the right moment to offer "want me to fix this while you're here?"

When a developer ticks a checkbox, a workflow detects the edit and kicks off a Devin session. Devin creates a branch, writes a repro test, fixes the code, runs the test suite, and opens a PR. The orchestrator monitors the session and reports success/failure back on the nudge comment.

### Flow

```
PR opened → nudge comment lists matched issues (with checkboxes for fixable bugs)
  → developer ticks checkbox for issue #N
    → devin-fix.yml detects the edit (old body vs new body diff)
      → orchestrator fetches triage card from issue #N's triage comment
      → orchestrator fetches issue #N title/body from GitHub API
      → Devin session started with fix prompt
      → poll until finished / blocked / timed out
      → check if Devin opened a PR on branch devin/fix-issue-N
      → update nudge comment with ✅ or ❌ result for issue #N
      → apply label on issue #N (devin:fix-attempted or devin:fix-failed)
```

### Acceptance criteria
- [x] The PR nudge renderer (Story 6) conditionally includes a per-issue auto-fix checkbox when the issue qualifies (bug, no open questions, confidence ≥ 0.7).
- [x] Issues that are `unclear`, `question`, have unanswered questions, or have confidence < 0.7 do **not** show a checkbox (but are still listed in the nudge).
- [x] A GitHub Actions workflow exists at `.github/workflows/devin-fix.yml` triggered on `issue_comment: [edited]` for PR comments.
- [x] The workflow's `if` guard checks:
  - The comment is on a pull request (`github.event.issue.pull_request` exists).
  - The comment contains the nudge marker (`<!-- devin-pr-nudge:v1`).
  - A checkbox was newly ticked (present in new body but not in previous body).
- [x] When triggered, the workflow:
  1. Compares old vs new comment body to detect which issue checkbox(es) changed from `[ ]` to `[x]`.
  2. For each newly-ticked issue number:
     a. Fetches the triage card from the issue's triage comment (not from the nudge comment).
     b. Fetches issue title/body from the GitHub API.
     c. Starts a Devin session with a fix prompt that instructs Devin to:
        - Read the triage card and issue context.
        - Write a reproduction test that demonstrates the bug.
        - Fix the code.
        - Verify the fix passes the repro test and the existing test suite.
        - Create a branch (`devin/fix-issue-{number}`) and open a PR linking back to the issue.
     d. Polls until the session finishes (or times out / fails).
- [x] On success (Devin finishes + PR opened):
  - The orchestrator updates the nudge comment with a "✅ Auto-fix for #N" section linking to the PR.
  - The label `devin:fix-attempted` is applied to the **issue**.
- [x] On failure (Devin blocked, timed out, or no PR created):
  - The orchestrator updates the nudge comment with a "❌ Auto-fix failed for #N" section containing:
    - What Devin tried.
    - Where it got stuck.
    - Pointers for manual investigation.
  - The label `devin:fix-failed` is applied to the **issue**.
- [x] The fix flow never runs on issues without a triage card.
- [x] Multiple checkboxes can be ticked in a single edit — the orchestrator processes each one.
- [x] Unit tests cover: checkbox detection (with issue number extraction), triage card fetching from issue comments, prompt building, success/failure comment rendering, nudge comment update, full attempt_fix flow (92 tests passing).

### Verification
- On a PR that nudges a fixable bug: tick the checkbox → Devin session starts → PR opened or failure report posted on the nudge comment.
- On a PR that nudges a vague/unclear issue: no checkbox appears in the nudge (informational only).
- On a failed fix: failure message with pointers appears on the nudge comment, `devin:fix-failed` label on the issue.

### Blocked until answered
1. Can the workflow have `contents: write` and `pull-requests: write` permissions?
2. Branch naming convention for fix PRs (recommended: `devin/fix-issue-{number}`)?
3. Should the fix prompt instruct Devin to run the full test suite, or only a targeted repro test?
4. Timeout for the fix session (longer than triage — recommended: 15–20 minutes)?
5. Should fix mode work for `feature-request` too, or bugs only?

**Recorded answers:**
- Write permissions: Yes — `contents: write` and `pull-requests: write` permitted.
- Branch naming: `devin/fix-issue-{number}` convention confirmed.
- Test scope: Both — targeted repro test first, then full test suite to catch regressions.
- Fix timeout: 15–20 minutes confirmed.
- Feature-request fix: Bugs only — `feature-request`, `question`, and `unclear` do not get the checkbox.

---

## Story 8 — Devin API deep integration

As a **VP Engineering evaluating this PoC**, I want **the integration to use Devin's full API surface — not just `prompt`**, so that **it's clear the team understands the platform deeply and has thought about production-readiness (cost control, observability, structured contracts, reusable playbooks)**.

Right now `create_session()` sends only `{ "prompt": "..." }`. The Devin v1 API accepts 12 parameters on session creation and returns rich metadata (including the PR URL) on the response — we use almost none of it. This story upgrades every Devin API call to use the right features.

### Design

#### 1. Structured Output Schema (triage sessions)

We already have `orchestrator/schemas/triage_card.schema.json` and already check `session_data.get("structured_output")` in `triage.py`. But we never **pass the schema to the API**. Adding `structured_output_schema` to `create_session()` tells Devin to validate its output server-side and return it in a dedicated field — no more fishing through messages for JSON.

```python
devin.create_session(
    prompt=prompt,
    structured_output_schema=triage_schema,  # JSON Schema Draft 7, max 64KB
)
```

This is Pattern D from the reference doc: *"Use Structured Output prompts to force Devin to return valid JSON."*

#### 2. Native PR detection (fix sessions)

`GET /v1/sessions/{id}` returns `pull_request: { url }` when Devin opens a PR. We currently search the GitHub API for a branch named `devin/fix-issue-{N}` — this is unnecessary. Using the native field is simpler, faster, and idiomatic.

```python
session_data = devin.poll_session(session_id)
pr_url = (session_data.get("pull_request") or {}).get("url")
```

The existing `_find_fix_pr()` GitHub API branch search is removed entirely — the native field is the single source of truth.

#### 3. Tags, titles, and cost controls

Every session gets metadata for observability and cost management:

| Parameter | Triage session | Fix session |
|---|---|---|
| `title` | `"Triage: Issue #42 — Off-by-one"` | `"Fix: Issue #42 — Off-by-one"` |
| `tags` | `["triage", "issue-42"]` | `["fix", "issue-42", "pr-5"]` |
| `max_acu_limit` | `5` | `10` |

A VP Engineering audience will notice cost controls and observability hooks — these say "I thought about running this in production."

#### 4. Playbook creation (programmatic)

The Devin API has `POST /v1/playbooks` (`title`, `body`). We create two reusable playbooks:

- **"Bug Triage"** playbook — the triage procedure (currently inlined in `prompt_builder.py`).
- **"Bug Fix"** playbook — the fix procedure (currently inlined in `fix_prompt_builder.py`).

Playbooks are created once (idempotent by title lookup), then referenced via `playbook_id` on `create_session()`. This shows we understand Devin's **reusable instruction system** — playbooks are how orgs standardize agent behavior at scale.

The raw prompt still carries issue-specific context (issue body, triage card, affected paths). The playbook carries the *procedure* (steps, verification, constraints). Clean separation of concerns.

#### 5. Idempotent sessions

`create_session(idempotent=True)` prevents duplicate sessions if a GitHub Actions workflow re-runs. Matches our idempotent-comments philosophy.

### Acceptance criteria
- [ ] **Structured output**: `triage.py` passes the triage card JSON Schema to `create_session()` via the `structured_output_schema` parameter. The `_extract_triage_card()` function still checks `structured_output` first (already does), but now the field is populated by the API rather than by luck.
- [ ] **Native PR detection**: `devin_fix.py` reads `session_data["pull_request"]["url"]` from the Devin session response. The old `_find_fix_pr()` GitHub API branch search is deleted.
- [ ] **Session titles**: Both triage and fix sessions pass a descriptive `title` derived from the issue number and title.
- [ ] **Session tags**: Both triage and fix sessions pass `tags` for filtering/observability (e.g., `["triage", "issue-42"]`).
- [ ] **ACU limit**: Both triage and fix sessions pass `max_acu_limit` (configurable, defaults: 5 for triage, 10 for fix).
- [ ] **Idempotent flag**: Fix sessions pass `idempotent=True` to prevent duplicate sessions on workflow re-run.
- [ ] **Playbooks**: A helper module at `orchestrator/playbook_manager.py` creates or retrieves (by title) a "Bug Triage" and "Bug Fix" playbook via the Devin API. `triage.py` and `devin_fix.py` pass the corresponding `playbook_id` to `create_session()`.
- [ ] **`DevinClient` extended**: `create_session()` accepts all new keyword args (`structured_output_schema`, `tags`, `title`, `max_acu_limit`, `idempotent`, `playbook_id`) and passes them through to the API payload.
- [ ] **Tests updated**: Existing tests still pass. New unit tests cover:
  - `create_session` passes through new parameters in the request body.
  - PR detection reads `pull_request.url` from session data (no GitHub API fallback).
  - Playbook manager create-or-get logic (mocked API).
  - Structured output extraction when the API populates `structured_output`.
- [ ] All existing tests still pass (≥92 tests).

### Verification
- Trigger triage on a test issue → Devin session created with `structured_output_schema`, `title`, `tags`, `max_acu_limit`, and `playbook_id` visible in API logs.
- Trigger auto-fix → session uses native `pull_request` field for PR detection, has `idempotent=True`, uses fix playbook.
- Run `pytest` → all tests pass.

### Blocked until answered
1. Confirm the Devin API key has permission to create playbooks (org-level vs personal key — `apk_` vs `apk_user_`)?
2. ACU limits: are `5` (triage) and `10` (fix) reasonable defaults, or should they be higher for safety?
3. Should playbooks be created on every run (idempotent by title) or once during setup and hardcoded?

**Recorded answers:**
- Playbook API access: _unanswered_
- ACU limits: _unanswered_
- Playbook creation strategy: _unanswered_

