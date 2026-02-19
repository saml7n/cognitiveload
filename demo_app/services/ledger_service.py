from typing import List
import datetime
from demo_app.models.ledger import LedgerEntry, TransactionType, Priority

# In-memory store
_ledger = [
    LedgerEntry(id=1, amount=100.0, description="Initial Deposit", type=TransactionType.CREDIT, priority=Priority.MEDIUM, date=datetime.date(2024, 1, 1)),
    LedgerEntry(id=2, amount=50.0, description="Office Supplies", type=TransactionType.DEBIT, priority=Priority.HIGH, date=datetime.date(2024, 1, 2)),
]

def list_entries(sort_by_priority: bool = False) -> List[LedgerEntry]:
    """
    Returns all ledger entries.
    If sort_by_priority is True, entries are sorted by priority (HIGH first).
    Bug B (Vague): Sorting logic is flawed. High priority items are accidentally pushed to the bottom.
    """
    _priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    results = list(_ledger)
    if sort_by_priority:
        results.sort(key=lambda x: _priority_order[x.priority])
    return results

def add_entry(entry: LedgerEntry) -> LedgerEntry:
    if any(e.id == entry.id for e in _ledger):
        raise ValueError("Entry ID already exists")
    _ledger.append(entry)
    return entry

def get_ledger_contents():
    return _ledger
