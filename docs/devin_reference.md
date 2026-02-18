# Devin API Solution Architecture

This document is a technical reference for building integrations with Devin. It synthesizes core API mechanics, advanced capabilities, and architectural patterns derived from the [official docs](https://docs.devin.ai/api-reference), the [QA repo](https://github.com/CognitionAI/qa-devin), and the [Automatic PR Reviews blog](https://cognition.ai/blog/devin-101-automatic-pr-reviews-with-the-devin-api).

## 1. Core Capabilities

Devin is not just a chatbot; it is an autonomous agent with a full sandboxed environment.
*   **Shell**: Full Linux terminal access. Can install packages (`apt`, `pip`), run compilers, and execute tests.
*   **Editor**: Can read/write files, navigate large codebases, and use `grep`/`find`.
*   **Browser**: A real Chromium instance. Can log into web apps (using secrets), browse documentation, and verify UI changes visually.
*   **Planner**: Maintains a dynamic "Step" list, self-correcting when it encounters errors (e.g., "Permission denied" -> "I will use sudo").

## 2. API Mechanics

### Authentication & Headers
```bash
Authorization: Bearer <YOUR_KEY>
Content-Type: application/json
```

### The Session Lifecycle
A "Session" is the fundamental unit of work. It is stateful and asynchronous.
1.  **Start (`POST /v1/sessions`)**: returns `session_id`.
2.  **Poll (`GET /v1/sessions/{id}`)**: Check `status_enum`.
    *   `starting`: Booting up.
    *   `working`: Agent is executing steps.
    *   `blocked`: Agent needs user input (see "Human-in-the-Loop").
    *   `finished`: Task complete.
    *   `stopped`: Error or manual stop.
3.  **Interact (`POST /v1/sessions/{id}/messages`)**: Send feedback or new instructions to a running session.

### Context Management
*   **Repositories**: Best practice is to instruct Devin to `git clone <url>` in the prompt. This gives full git history.
*   **Snapshots**: Create a "warm" session (deps installed, repo cloned), then use `snapshot_id` to spawn new sessions instantly. Critical for latency-sensitive or parallel tasks.
*   **Playbooks**: Define standard operating procedures (SOPs) to ensure consistent behavior across sessions.

## 3. Advanced Architectural Patterns

### Pattern A: The "Agentic Repair" Loop (Quality Assurance)
*Source: Cognition QA Repo*
Instead of "fix this," use a **Reproduction -> Fix -> Verify** loop.
1.  **Reproduction**: Instruct Devin to creates a script (e.g., `repro.py`) that demonstrates the bug.
    *   *Prompt*: "Create a reproduction script for issue X. Run it to confirm failure."
2.  **Fix**: Devin edits the code.
3.  **Verify**: Devin runs `repro.py` again.
    *   *Constraint*: The session is only considered "Success" if the reproduction script passes.
4.  **External Harness**: A wrapper script can poll the session and only mark the ticket "Resolved" if the final log shows the test passing.

### Pattern B: CI/CD & PR Reviews
*Source: Automatic PR Reviews Blog*
Integrate Devin into GitHub Actions/GitLab CI.
1.  **Trigger**: Event (e.g., `pull_request`) fires a workflow.
2.  **Context Construction**:
    *   The workflow script fetches the list of *changed files* (using `git diff --name-only`).
    *   Passes this list to Devin: "Review only these files: [A, B, C]."
3.  **Safety Guardrails**:
    *   **Pre-push Hooks**: Install a git hook in the Devin environment to prevent it from pushing directly to `main` or specific protected branches.
    *   **Idempotency**: Logic to check if a comment was already posted to avoid spamming.
4.  **Feedback**: The integration parses Devin's output (or specialized tool calls) to post inline comments directly to the generic Code Hosting API.

### Pattern C: Browser-Based Testing
*Source: QA Scenarios*
Use Devin for End-to-End (E2E) testing where code alone isn't enough.
*   **Scenario**: "Log into our staging site and verify the dashboard loads."
*   **Secrets**: Use the API to securely inject credentials (MFA, passwords) so Devin can authenticate.
*   **Visual Logic**: Devin can "see" rendered HTML/CSS issues that unit tests miss.

### Pattern D: The Triage & Migration Factory
*   **Triage**:
    *   Monitor Issue Tracker -> Start Session ("Investigate...") -> Poll for `blocked` (User Input needed?) -> Output specific JSON summary.
    *   *Key*: Use **Structured Output** prompts to force Devin to return valid JSON for your backend to parse.
*   **Migration (Parallelism)**:
    *   Use **Snapshots** to prepare the environment.
    *   Spawn N parallel sessions (one per file/module).
    *   Aggregate results into a single PR.

## 4. Quick Reference: Endpoints

| Method | Endpoint | Use Case |
| :--- | :--- | :--- |
| `POST` | `/v1/sessions` | Start work. Body: `{ "prompt": "...", "snapshot_id": "..." }` |
| `GET` | `/v1/sessions/{id}` | Poll status/logs. |
| `POST` | `/v1/sessions/{id}/messages` | Human-in-the-loop feedback ("blocked" state). |
| `POST` | `/v1/sessions` (batch) | *Check docs for batch/parallel capabilities if applicable.* |

## 5. Implementation Checklist

- [ ] **Auth**: Headers set correctly?
- [ ] **Polling**: Exponential backoff implemented?
- [ ] **Context**: Repo cloned? specific files mentioned?
- [ ] **Safety**: Is Devin restricted from destructive actions (e.g., pushing to main)?
- [ ] **Output**: Are you parsing structured output or just reading logs?
