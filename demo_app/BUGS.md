# Seeded Bugs for Demo

This file records the intentional bugs for the bot to triage. These are used to verify the "Triage Intelligence" and "PR-Time Nudges" workflows.

---

### Bug A: Off-by-one error in count
- **Type:** Clear.
- **Description:** `GET /summary` endpoint returns an incorrect `entry_count`. It always returns one less than the actual number of entries in the ledger.
- **Root Cause:** Uses `len(ledger) - 1` instead of `len(ledger)`.
- **Affected File:** `demo_app/services/stats_service.py`
- **Verification:** Create 2 entries, expect 2 count, get 1.

---

### Bug B: Sorting logic is flawed
- **Type:** Vague.
- **Description:** Users report that "Urgent items aren't showing at the top" when they sort by priority.
- **Root Cause:** The `list_entries` function uses `results.sort(key=lambda x: x.priority.value, reverse=False)`. Since PRIORITY values are "high", "low", "medium", alphabetical sorting pushes "high" to the middle.
- **Affected File:** `demo_app/services/ledger_service.py`
- **Verification:** Run `GET /entries?sort_by_priority=true` and confirm "HIGH" priority items are not at the top.

---

### Bug C: Hard-to-repro global state drift
- **Type:** Hard to Repro / Drift.
- **Description:** "Balances are drifting slightly over time, and every summary check returns a slightly different number."
- **Root Cause:** A global fee multiplier is being improperly incremented on every access in `get_current_fee_multiplier`.
- **Affected File:** `demo_app/core/config.py`
- **Verification:** Call `GET /summary` multiple times consecutively. The `total_balance` will drift upwards without any changes to the ledger.
