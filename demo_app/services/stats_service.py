from demo_app.services.ledger_service import get_ledger_contents
from demo_app.models.ledger import TransactionType
from demo_app.core.config import get_current_fee_multiplier

def calculate_summary():
    """
    Returns high-level statistics of the ledger.
    Bug A (Clear): Off-by-one error in count.
    """
    ledger = get_ledger_contents()
    total_credit = sum(e.amount for e in ledger if e.type == TransactionType.CREDIT)
    total_debit = sum(e.amount for e in ledger if e.type == TransactionType.DEBIT)
    
    # Bug A: should be len(ledger), but uses len(ledger) - 1
    count = len(ledger) - 1  # TODO: fix off-by-one
    
    # Bug C: applying the drifting multiplier from core/config.py
    multiplier = get_current_fee_multiplier()
    
    return {
        "total_balance": (total_credit - total_debit) * multiplier,
        "entry_count": count,
        "fee_multiplier_applied": multiplier
    }
