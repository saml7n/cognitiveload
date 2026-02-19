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
              → Story 8: Demo runbook + seeded scenarios (Loom script, covers full loop incl. fix mode)
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
- PR comment style: Informational only — no checkboxes; hint "Consider fixing while you're in this area."

---

## Story 7 — Devin auto-fix workflow (checkbox-triggered)

As a **senior engineer**, I want to **tick a checkbox on a triaged issue and have Devin attempt to reproduce, fix, and commit a solution**, so that **small-to-medium bugs get fixed without waiting weeks for someone to pick them up**.

This is where we let Devin do the heavy lifting — including its native GitHub integration for branching, committing, and opening PRs.

### Design

The triage comment (Story 5) already renders a card. This story adds a conditional "attempt fix" checkbox:

```markdown
### 🔧 Auto-fix
- [ ] Attempt auto-fix with Devin
```

The checkbox is **only shown** when the issue is actionable:
- Classification is `bug` (not `unclear`, `question`, or `feature-request`).
- The `questions` array is empty (no outstanding clarification needed).
- Confidence is ≥ 0.7.

When a user edits the triage comment to tick the checkbox (`- [x]`), a new workflow detects it and kicks off a Devin session with a "fix" prompt. Devin uses its native GitHub app connection to create a branch, commit the fix, and open a PR — the orchestrator just starts the session, monitors progress, and reports the outcome back on the issue.

### Acceptance criteria
- [ ] The triage comment renderer (Story 5) conditionally includes the auto-fix checkbox when the issue qualifies (bug, no open questions, confidence ≥ 0.7).
- [ ] Issues that are `unclear`, `question`, or have unanswered questions do **not** show the checkbox.
- [ ] A GitHub Actions workflow exists at `.github/workflows/devin-fix.yml` triggered on `issue_comment: [edited]`.
- [ ] When triggered, the workflow:
  1. Detects the checkbox state change (`- [ ]` → `- [x]`).
  2. Verifies the issue has the `devin:triaged` label (guard rail).
  3. Starts a Devin session with a fix prompt that instructs Devin to:
     a. Read the triage card and issue context.
     b. Write a reproduction test/script that demonstrates the bug.
     c. Fix the code.
     d. Verify the fix passes the repro test and the existing test suite.
     e. Create a branch (`devin/fix-issue-{number}`) and open a PR linking back to the issue.
  4. Polls until the session finishes (or times out / fails).
- [ ] On success (Devin finishes + PR opened):
  - The orchestrator updates the triage comment with a "✅ Fix attempted" section linking to the PR.
  - The label `devin:fix-attempted` is applied.
- [ ] On failure (Devin blocked, timed out, or no PR created):
  - The orchestrator updates the triage comment with a "❌ Auto-fix failed" section containing:
    - What Devin tried.
    - Where it got stuck.
    - Pointers for manual investigation (relevant files, repro steps attempted).
  - The label `devin:fix-failed` is applied.
- [ ] The fix flow never runs on issues without a triage card.
- [ ] Unit tests cover: checkbox detection, prompt building, success/failure comment rendering.

### Verification
- On a triaged clear-bug issue: tick the checkbox → Devin session starts → PR opened or failure report posted.
- On a vague/unclear issue: checkbox is not present in the triage comment.
- On a triaged issue where the fix fails: failure message with pointers appears.

### Blocked until answered
1. Can the workflow have `contents: write` and `pull-requests: write` permissions?
2. Branch naming convention for fix PRs (recommended: `devin/fix-issue-{number}`)?
3. Should the fix prompt instruct Devin to run the full test suite, or only a targeted repro test?
4. Timeout for the fix session (longer than triage — recommended: 15–20 minutes)?
5. Should fix mode work for `feature-request` too, or bugs only?

**Recorded answers:**
- Write permissions: _unanswered_
- Branch naming: _unanswered_
- Test scope: _unanswered_
- Fix timeout: _unanswered_
- Feature-request fix: _unanswered_

---

## Story 8 — Demo runbook and seeded scenarios

As a **candidate recording a Loom demo**, I want **a step-by-step runbook with predictable outcomes**, so that **the demo is crisp and tells a clear story in under 10 minutes**.

The runbook now covers the full loop: triage → nudge → auto-fix.

### Acceptance criteria
- [ ] A runbook exists at `docs/demo_runbook.md` with exact steps:
  - Step 1: Show repo structure and explain the system (triage → nudge → fix pipeline).
  - Step 2: Create Issue A (clear bug) → triage card appears with auto-fix checkbox.
  - Step 3: Create Issue B (vague bug) → clarification questions appear, **no** auto-fix checkbox.
  - Step 4: Open a PR touching Bug A's affected path → nudge comment appears linking to Issue A.
  - Step 5: Tick the auto-fix checkbox on Issue A → Devin attempts fix → PR opened or failure report.
- [ ] Pre-written issue bodies exist in `docs/demo_issues/` (one file per issue, ready to copy-paste).
- [ ] A pre-written PR description and branch change set exist in `docs/demo_pr/`.
- [ ] Each step documents the expected outcome (screenshot or text description).
- [ ] The runbook includes timing estimates per step and talking points.

### Verification
- Walk through the runbook end-to-end. Each step produces the documented outcome.

### Blocked until answered
1. Create issues live during Loom or pre-create them?
2. Any specific talking points required for the video (e.g., "why Devin vs other agents")?
3. Include Slack notifications as a bonus, or keep it GitHub-only?

**Recorded answers:**
- Issue creation approach: _unanswered_
- Talking points: _unanswered_
- Slack: _unanswered_
