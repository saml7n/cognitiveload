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
    Bug B (Vague): Sorting logic is flawed. High priority items are accidentally pushed to the bottom.
    """
    results = list(_ledger)
    if sort_by_priority:
        # Intentionally flawed sort: HIGH should be first, but we reverse it.
        # priority levels: low, medium, high (alphabetical: h, l, m)
        results.sort(key=lambda x: x.priority.value, reverse=False) 
    return results

def add_entry(entry: LedgerEntry) -> LedgerEntry:
    if any(e.id == entry.id for e in _ledger):
        raise ValueError("Entry ID already exists")
    _ledger.append(entry)
    return entry

def get_ledger_contents():
    return _ledger
