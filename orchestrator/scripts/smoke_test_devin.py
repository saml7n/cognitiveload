import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from orchestrator.devin_client import DevinClient

# Load .env from the repo root (two levels up from this script)
_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(_repo_root / ".env")

def main():
    api_key = os.environ.get("DEVIN_API_KEY")
    if not api_key:
        print("Error: DEVIN_API_KEY not set. Add it to a .env file at the repo root.")
        sys.exit(1)

    client = DevinClient(api_key=api_key)
    
    prompt = "Hello! This is a smoke test for a Devin API client wrapper. Please respond with the word 'Ready' and then finish the session immediately. Do not perform any other tasks."
    
    print(f"Creating session with prompt: '{prompt}'...")
    try:
        session_id = client.create_session(prompt)
        print(f"Session created: {session_id}")
        print(f"View in dashboard: https://app.devin.ai/sessions/{session_id}")
        
        print("Polling session (timeout 5 mins)...")
        result = client.poll_session(session_id)
        
        status = result.get("status_enum")
        print("\n--- Session Result ---")
        print(f"Status enum: {status}")
        print(f"Status text: {result.get('status')}")
        
        # Both 'finished' and 'blocked' prove the client works end-to-end.
        # 'blocked' means Devin reached a decision point and is awaiting human input —
        # this is expected when running without a connected repo or structured task.
        if status in ("finished", "blocked"):
            print(f"\n✅ Smoke test PASSED: client successfully created a session, polled, and received terminal state '{status}'.")
        else:
            print(f"\n⚠️  Unexpected terminal state: '{status}'. Check the dashboard.")

    except Exception as e:
        print(f"\n❌ Smoke test FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
