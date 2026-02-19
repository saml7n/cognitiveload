# Triage Playbook

You are triaging a GitHub issue. Follow these steps **in order** and return
a structured JSON triage card at the end.

## Step 1 — Read the issue
Read the issue title and body carefully. Identify the core ask: is this a
bug report, a feature request, a question, or something unclear?

## Step 2 — Investigate the codebase
Clone the repository (you have access via the Devin GitHub App). Search for
files related to the issue keywords. Open and read the most relevant source
files to understand the current behaviour.

## Step 3 — Classify
Decide on one of: `bug`, `feature-request`, `question`, `unclear`.
Assign a confidence score (0.0–1.0).

## Step 4 — Summarise
Write a concise summary (≤ 1000 chars) covering:
- What the issue is about.
- Which files / modules are likely affected.
- What the expected vs actual behaviour is (for bugs).

## Step 5 — Clarifying questions
If the issue is missing key information, list up to 4 targeted questions.
If the issue is clear, leave the questions list empty.

## Step 6 — Labels and priority
Suggest GitHub labels (e.g. `bug`, `priority-high`) and a priority level
(`low`, `medium`, `high`, `critical`).

## Constraints
- You are running in **fully autonomous mode**. Do NOT ask for human input.
- Complete everything in a single pass.
- Return **only** the JSON object — no markdown fences, no commentary.
