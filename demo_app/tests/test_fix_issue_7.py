import datetime
from demo_app.models.ledger import LedgerEntry, TransactionType, Priority
from demo_app.services.ledger_service import list_entries, get_ledger_contents


def test_priority_sort_high_first():
    """HIGH priority entries should appear before MEDIUM and LOW when sorting by priority."""
    ledger = get_ledger_contents()
    original = list(ledger)
    ledger.clear()
    try:
        ledger.append(LedgerEntry(id=901, amount=10.0, description="Low item", type=TransactionType.CREDIT, priority=Priority.LOW, date=datetime.date(2024, 1, 1)))
        ledger.append(LedgerEntry(id=902, amount=20.0, description="High item", type=TransactionType.CREDIT, priority=Priority.HIGH, date=datetime.date(2024, 1, 2)))
        ledger.append(LedgerEntry(id=903, amount=30.0, description="Medium item", type=TransactionType.CREDIT, priority=Priority.MEDIUM, date=datetime.date(2024, 1, 3)))

        results = list_entries(sort_by_priority=True)
        priorities = [e.priority for e in results]
        assert priorities == [Priority.HIGH, Priority.MEDIUM, Priority.LOW], (
            f"Expected [HIGH, MEDIUM, LOW] but got {priorities}"
        )
    finally:
        ledger.clear()
        ledger.extend(original)
