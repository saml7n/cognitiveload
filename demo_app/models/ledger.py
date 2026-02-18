from pydantic import BaseModel
from enum import Enum
import datetime

class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class LedgerEntry(BaseModel):
    id: int
    amount: float
    description: str
    type: TransactionType
    priority: Priority = Priority.LOW
    date: datetime.date
