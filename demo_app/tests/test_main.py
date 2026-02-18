from fastapi.testclient import TestClient
from demo_app.main import app
import pytest

client = TestClient(app)

def test_read_root():
    response = client.get("/entries")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_create_entry():
    new_entry = {
        "id": 100,
        "amount": 250.0,
        "description": "Test Entry",
        "type": "credit",
        "priority": "low",
        "date": "2024-02-18"
    }
    response = client.post("/entries", json=new_entry)
    assert response.status_code == 200
    assert response.json()["id"] == 100

def test_summary_exists():
    response = client.get("/summary")
    assert response.status_code == 200
    assert "total_balance" in response.json()
    assert "entry_count" in response.json()
