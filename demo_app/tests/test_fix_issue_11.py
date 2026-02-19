import datetime
from demo_app.models.ledger import LedgerEntry, TransactionType, Priority
from demo_app.services.ledger_service import list_entries, get_ledger_contents


def test_sort_by_priority_high_first():
    """High priority entries must appear before medium and low when sorting by priority."""
    ledger = get_ledger_contents()
    original_len = len(ledger)

    ledger.append(
        LedgerEntry(id=900, amount=10.0, description="Low task", type=TransactionType.DEBIT, priority=Priority.LOW, date=datetime.date(2024, 3, 1))
    )
    ledger.append(
        LedgerEntry(id=901, amount=20.0, description="High task", type=TransactionType.CREDIT, priority=Priority.HIGH, date=datetime.date(2024, 3, 2))
    )
    ledger.append(
        LedgerEntry(id=902, amount=30.0, description="Medium task", type=TransactionType.DEBIT, priority=Priority.MEDIUM, date=datetime.date(2024, 3, 3))
    )

    try:
        sorted_entries = list_entries(sort_by_priority=True)
        priorities = [e.priority for e in sorted_entries]

        for i in range(len(priorities) - 1):
            assert _priority_rank(priorities[i]) >= _priority_rank(priorities[i + 1]), (
                f"Entry at index {i} ({priorities[i]}) should not come before entry at index {i+1} ({priorities[i+1]})"
            )
    finally:
        del ledger[original_len:]


def _priority_rank(p: Priority) -> int:
    return {Priority.HIGH: 3, Priority.MEDIUM: 2, Priority.LOW: 1}[p]
