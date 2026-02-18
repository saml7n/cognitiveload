# Agent Operating Instructions (Story-Driven)

These instructions apply to any coding agent working in this repository.

## Non-negotiables

1. **Story-gated work only**
   - Before making any code change, read the relevant story in:
     - `docs/stories_client_a.md`
   - You must identify the active story (e.g., “Story 2 — GitHub Action: Issue Intake”).
   - You must confirm that all items under **“Need from you before I start”** for that story have been answered and recorded in `docs/stories_client_a.md`.
   - If any prerequisite answer is missing/ambiguous, **stop** and ask the user to provide it, then require the story doc to be updated before proceeding.

2. **One story at a time**
   - Do not begin a new story until the current story meets its acceptance criteria, is tested, and is committed.

3. **Test before moving on**
   - Every story must have a concrete verification step.
   - Prefer automated tests (`pytest`, etc.). If the repo has no tests for the story’s scope, add minimal tests or a deterministic verification script as part of that story.
   - Run tests before finalizing the story.

4. **One commit per story**
   - Each story’s implementation must be contained in a single commit.
   - Commit message format:
     - `story-<N>: <short title>`
     - Example: `story-2: issue intake workflow`
   - The commit must include:
     - code changes
     - tests / verification assets for that story
     - story doc updates that mark the story as done (see below)

5. **Update the story doc as part of completion**
   - When a story is complete, update `docs/stories_client_a.md` with:
     - confirmation the acceptance criteria were met
     - what tests/verification were run and the result
     - the commit hash

## Working method (repeat for every story)

### A) Pre-flight (no code yet)
- Read the story section in `docs/stories_client_a.md`.
- Restate the acceptance criteria as a checklist.
- Verify prerequisites are answered in the story doc.
- If prerequisites are missing: ask for them; do not start implementation.

### B) Implement (minimal surface area)
- Make the smallest set of changes required to satisfy acceptance criteria.
- Keep changes localized; avoid refactors unless required.
- Use clear names and straightforward control flow.

### C) Verify
- Run the most targeted tests/commands for the story.
- If verification requires GitHub Actions behavior, also provide a local dry-run strategy (e.g., run the orchestrator against a saved event payload).

### D) Commit
- Ensure working tree is clean except for intended changes.
- Create exactly one commit for the story.

### E) Close out
- Update `docs/stories_client_a.md` with completion evidence and commit hash.

## Coding style

- **Minimalistic, readable, neat**: prefer simple functions and explicit logic.
- Avoid clever abstractions, metaprogramming, and premature generalization.
- Keep modules small; keep functions focused.
- Use consistent naming; avoid one-letter variables.
- Prefer standard library solutions where reasonable.
- Prefer deterministic behavior (idempotent updates, stable markers, fixed schemas).

## Safety defaults for this project

- Default to **comment/label only** unless the story explicitly authorizes code changes/PR creation.
- Avoid destructive operations (closing issues, deleting branches) unless explicitly required by story acceptance criteria and gated prerequisites are satisfied.
