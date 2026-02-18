import requests
import time
import os
from typing import Dict, Any, Optional

class DevinClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.devin.ai/v1"):
        """
        Initializes the Devin API client.
        :param api_key: The API key for authentication. Defaults to DEVIN_API_KEY environment variable.
        :param base_url: The base URL for the API. Defaults to https://api.devin.ai/v1.
        """
        self.api_key = api_key or os.environ.get("DEVIN_API_KEY")
        if not self.api_key:
            raise ValueError("DEVIN_API_KEY is required")
        
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def create_session(self, prompt: str, snapshot_id: Optional[str] = None, **kwargs) -> str:
        """
        Starts a new Devin session.
        :param prompt: The initial instruction for Devin.
        :param snapshot_id: Optional ID of a snapshot to start from.
        :param kwargs: Additional arguments to pass to the API.
        :return: The session_id of the created session.
        """
        payload = {
            "prompt": prompt,
            **kwargs
        }
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id

        try:
            resp = requests.post(f"{self.base_url}/sessions", json=payload, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            return data["session_id"]
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Provide a more specific error for authentication failure
                raise ValueError("Invalid Devin API Key") from e
            raise

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves the current state of a session.
        :param session_id: The ID of the session to retrieve.
        :return: A dictionary containing session details.
        """
        resp = requests.get(f"{self.base_url}/sessions/{session_id}", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def send_message(self, session_id: str, message: str) -> None:
        """
        Sends a message to an existing session.
        :param session_id: The ID of the session.
        :param message: The message content to send.
        """
        # The endpoint for sending a message is /sessions/{session_id}/messages
        # We need to construct the payload correctly.
        # Based on docs (though inferred here), usually just a message string or object.
        # Assuming the API expects {"message": "content"} or similar.
        # Check docs: POST /v1/sessions/{id}/messages
        # Body: { "message": "..." } - assumed standard
        payload = {"message": message}
        resp = requests.post(f"{self.base_url}/sessions/{session_id}/messages", json=payload, headers=self.headers)
        resp.raise_for_status()

    def poll_session(self, session_id: str, timeout: int = 300, interval: int = 5) -> Dict[str, Any]:
        """
        Polls a session until it reaches a terminal state (finished, stopped, blocked).
        :param session_id: The ID of the session to poll.
        :param timeout: Maximum time to wait in seconds.
        :param interval: Time to wait between checks in seconds.
        :return: The final session state dictionary.
        :raises TimeoutError: If the session does not reach a terminal state within the timeout.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            session_data = self.get_session(session_id)
            # The API documentation indicates "status_enum" provides the machine-readable status
            # Fallback to "status" if "status_enum" is missing, though v1 should have it.
            status = session_data.get("status_enum", session_data.get("status"))
            
            # Terminal states:
            # - finished: completed successfully
            # - stopped: stopped by user or error
            # - blocked: waiting for user input
            if status in ["finished", "stopped", "blocked"]:
                return session_data
            
            time.sleep(interval)
        
        raise TimeoutError(f"Session {session_id} timed out after {timeout} seconds")
