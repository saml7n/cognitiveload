# Solution Plan: Client A (FinServ Co) - Issue Intelligence + PR-Time Nudges

## 1. The Problem
**Client:** FinServ Co.
**Pain Point:** "Drowning in GitHub issues." 300+ open issues, mixed quality (bugs vs feature requests vs noise). Senior engineers lose focus to validation/triage. Junior engineers spend more time understanding tickets than fixing them.

**What this *really* means in practice:**
- The backlog grows because issues are unclear and require costly back-and-forth.
- Even when an issue is valid, it often won’t be fixed until someone is already touching that code.

**Goal:** Turn a wall of stale issues into a system where:
- Every issue gets a clear, structured triage summary (or targeted questions).
- Engineers get relevant “known issue” context at the moment they are already changing adjacent code.
- The process is low-noise and evidence-driven.

## 2. The Solution: "Issue Intelligence + PR-Time Nudges"
We will build a GitHub integration that continuously converts raw GitHub issues into structured, actionable knowledge (triage cards), then surfaces that knowledge to developers when it’s most useful: when they open a PR that touches related code.

This solves two problems at once:
1) **Understanding**: reduce time-to-comprehension via clarifying questions + triage cards.
2) **Resolution**: increase fix-throughput by nudging developers *during related PRs* with an evidence-backed summary and suggested next action.

### Key Capabilities (The "Wow" Factors)
1.  **Smart triage at scale (existing backlog + new issues)**: Devin produces a consistent “triage card” so issues are comparable.
2.  **Clarification instead of guesswork**: If the issue is unclear, Devin asks 2–4 targeted questions and applies `needs-info`.
3.  **Evidence-backed suggestions (when warranted)**: For well-specified bugs, Devin can propose repro steps (and optionally a repro script) and a likely fix path.
4.  **PR-time relevance (the non-obvious lever)**: When a PR touches related files, we comment with “known issue” context and a suggested action.
5.  **Low-noise + idempotent**: We post exactly one bot comment per issue/PR and update it on reruns.

### End State Workflows

#### A) Issue Intake: Clarify or Triage
1. **User opens Issue** (or labels it with `devin:triage`).
2. **Trigger**: GitHub Action fires → calls our Orchestrator.
3. **Devin session** produces a structured result:
    - If unclear: targeted questions + `needs-info`.
    - If clear: triage card + suggested labels + “affected paths” (files/folders likely involved).
4. **Output back to GitHub**:
    - One idempotent comment on the issue (updated on reruns).
    - Labels applied (e.g., `bug`, `area:auth`, `priority:med`, `devin:triaged`).

#### B) PR-Time Nudge: Surface Known Issues
1. **Developer opens/updates a PR**.
2. **Trigger**: GitHub Action fires on `pull_request` events.
3. Orchestrator matches PR changed files against triaged issues’ “affected paths”.
4. **Output back to GitHub**:
    - A single PR comment: “This PR touches code related to #123” + summary + suggested action.
    - Optionally: a checkbox decision prompt (fix now / defer / needs info).

## 3. Architecture

### Components
*   **Orchestrator (Python)**: A lightweight script that runs in GitHub Actions. It:
    *   Parses the GitHub event payload.
    *   Enforces policy (triage-only vs nudge vs fix mode).
    *   Starts Devin sessions (triage/investigation) and polls for completion.
    *   Writes results back to GitHub (comments, labels) in an idempotent way.
*   **Devin sessions**: The "agent" compute. They can clone the repo, inspect code, run tests, and produce structured triage output.
*   **GitHub Actions**: The real-time trigger mechanism for issues/PRs.
*   **State storage (PoC)**:
    *   Stored in GitHub itself via the bot comment (embedded JSON) + labels.
    *   (Optional) A single “Triage Dashboard” issue that the bot updates daily.

### Integration Flow
`GitHub Event` → `GitHub Action` → `Orchestrator` → `Devin API` → `GitHub (comments/labels)`

## 4. What "Devin connected to this GitHub repo" means (and how we’ll use it)
You mentioned Devin is already connected to this GitHub repo.

In practice, this usually means:
- Devin can access the repository content (including private repos) inside sessions without you manually pasting credentials.
- Depending on the integration level, Devin may also be able to open branches/PRs directly from its environment.

How we will leverage this in the PoC (safe + demo-friendly):
- We’ll still drive work from GitHub Actions + our orchestrator so the “real-time pipeline” story is clear.
- We’ll assume Devin can `git clone` the repo by URL from the session prompt (no extra auth ceremony).
- For writing comments/labels, our orchestrator will use `GITHUB_TOKEN` from Actions (least moving parts).
- For code changes/PRs, we’ll make this opt-in (label/command). If direct PR creation from Devin is not available in the API integration, we’ll have Devin output a patch/branch plan and let the orchestrator apply it.

## 5. Prerequisites (What we need)

Before we can start coding the solution, we need to gather/setup:

### A. Access & Secrets
*   [ ] **Devin API Key**: needed to start sessions.
*   [ ] **GitHub Token**: needed to post comments and labels (can use `GITHUB_TOKEN` from Actions).

### B. GitHub Repo Setup
*   [ ] Labels: `devin:triage`, `devin:triaged`, `needs-info`, `devin:fix` (optional), `devin:blocked` (optional).
*   [ ] Workflow permissions: allow the Action to write issues/PR comments and apply labels.
*   [ ] (Optional) Issue templates to encourage consistent bug reports.

### C. The "Target" Repo (Simulation)
Since we can't access FinServ's real monorepo, we need a **simulation repo** to demo this effectively.
*   [ ] **Demo Repo**: A small, realistic repo (e.g., a simple Todo App or Calculator) to run the triage bot *against*.
*   [ ] **Seeded Issues**: We need 3-4 specific issues to test:
    *   *Issue 1 (The easy bug)*: A clear bug with a simple fix.
    *   *Issue 2 (The ambiguity)*: A bug report missing steps (Devin should ask for info).
    *   *Issue 3 (The complex fail)*: A harder bug that Devin can repro but maybe not fix immediately.

### D. Matching Strategy for PR-Time Nudges
*   [ ] Decide on the “affected paths” format (e.g., list of file globs / folder prefixes).
*   [ ] Decide where it lives (recommended: embedded JSON in the bot’s issue comment).

### E. Orchestrator Boilerplate
*   [ ] **Python Environment**: `functions` or `scripts` folder.
*   [ ] **Devin Client**: Simple wrapper for `POST /sessions` and `GET /sessions/{id}`.
*   [ ] **GitHub Client**: wrapper for commenting, labeling, editing existing bot comments, and reading PR changed files.

## 6. Implementation Plan (Next Steps)

1.  **Scaffold**: Create `triage_orchestrator/` directory and basic Python entrypoint.
2.  **Define contracts**:
    *   JSON schema for the triage output (triage card + questions + affected paths).
    *   A stable bot comment marker so we update instead of spamming.
3.  **Issue workflow (real-time)**:
    *   Add `.github/workflows/issue-triage.yml` triggered by `issues` + `issue_comment`.
    *   Implement triage-only mode first (low risk).
4.  **PR workflow (real-time)**:
    *   Add `.github/workflows/pr-nudge.yml` triggered by `pull_request`.
    *   Implement matching logic (changed files ↔ affected paths) and PR comment update.
5.  **Optional: Fix mode**:
    *   Add `devin:fix` opt-in path that asks Devin for repro + fix plan or a PR.
6.  **Demo hardening**:
    *   Seed 3–4 issues with known outcomes (clarify vs triage).
    *   Ensure idempotency (rerun workflows without spam).
