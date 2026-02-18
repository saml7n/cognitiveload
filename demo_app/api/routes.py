from fastapi import APIRouter, HTTPException
from typing import List
from demo_app.models.ledger import LedgerEntry
from demo_app.services.ledger_service import list_entries, add_entry
from demo_app.services.stats_service import calculate_summary

router = APIRouter()

@router.get("/entries", response_model=List[LedgerEntry])
def get_entries(sort_by_priority: bool = False):
    return list_entries(sort_by_priority)

@router.get("/summary")
def get_summary():
    return calculate_summary()

@router.post("/entries", response_model=LedgerEntry)
def create_entry(entry: LedgerEntry):
    try:
        return add_entry(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
