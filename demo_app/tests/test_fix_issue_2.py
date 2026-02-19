from demo_app.services.stats_service import calculate_summary
from demo_app.services.ledger_service import get_ledger_contents


def test_entry_count_matches_ledger_length():
    """The summary entry_count must equal the actual number of ledger entries."""
    ledger = get_ledger_contents()
    summary = calculate_summary()
    assert summary["entry_count"] == len(ledger)
