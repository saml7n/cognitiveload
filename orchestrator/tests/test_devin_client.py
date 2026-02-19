import unittest
from unittest.mock import patch, MagicMock
import requests
from orchestrator.devin_client import DevinClient

class TestDevinClient(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.client = DevinClient(self.api_key)
        self.base_url = "https://api.devin.ai/v1"

    @patch('orchestrator.devin_client.requests.post')
    def test_create_session_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"session_id": "session_123"}
        mock_post.return_value = mock_response

        session_id = self.client.create_session("Test Prompt")

        self.assertEqual(session_id, "session_123")
        mock_post.assert_called_once_with(
            f"{self.base_url}/sessions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"prompt": "Test Prompt"}
        )

    @patch('orchestrator.devin_client.requests.post')
    def test_create_session_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        # Create exception and attach response
        http_error = requests.exceptions.HTTPError("Bad Request")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        
        mock_post.return_value = mock_response

        with self.assertRaises(Exception) as context:
            self.client.create_session("Test Prompt")
        
        self.assertIn("Bad Request", str(context.exception))

    @patch('orchestrator.devin_client.requests.get')
    def test_get_session_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "running"}
        mock_get.return_value = mock_response

        status = self.client.get_session("session_123")

        self.assertEqual(status, {"status": "running"})
        # The client uses shared headers which include Content-Type
        mock_get.assert_called_once_with(
            f"{self.base_url}/sessions/session_123",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )

    @patch('orchestrator.devin_client.requests.post')
    def test_send_message_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        self.client.send_message("session_123", "Hello")

        mock_post.assert_called_once_with(
            f"{self.base_url}/sessions/session_123/message",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"message": "Hello"}
        )

    @patch('orchestrator.devin_client.requests.get')
    def test_poll_session_finished(self, mock_get):
        # First call running, second call finished
        mock_response_running = MagicMock()
        mock_response_running.status_code = 200
        mock_response_running.json.return_value = {"status_enum": "running"}
        
        mock_response_finished = MagicMock()
        mock_response_finished.status_code = 200
        mock_response_finished.json.return_value = {"status_enum": "finished", "structured_output": {"result": "ok"}}

        mock_get.side_effect = [mock_response_running, mock_response_finished]

        with patch('time.sleep', return_value=None):  # Skip sleep
            result = self.client.poll_session("session_123")

        self.assertEqual(result, {"status_enum": "finished", "structured_output": {"result": "ok"}})
        self.assertEqual(mock_get.call_count, 2)

    @patch('orchestrator.devin_client.requests.get')
    def test_poll_session_timeout(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status_enum": "running"}
        mock_get.return_value = mock_response

        with patch('time.sleep', return_value=None):
             with self.assertRaises(TimeoutError):
                self.client.poll_session("session_123", interval=0.1, timeout=0.2)


class TestCreateSessionParams(unittest.TestCase):
    """Verify that create_session passes through all v1 API parameters."""

    def setUp(self):
        self.api_key = "test_api_key"
        self.client = DevinClient(self.api_key)
        self.base_url = "https://api.devin.ai/v1"

    def _mock_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"session_id": "sess_new"}
        mock_post.return_value = mock_resp

    @patch('orchestrator.devin_client.requests.post')
    def test_passes_structured_output_schema(self, mock_post):
        self._mock_success(mock_post)
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}

        self.client.create_session("prompt", structured_output_schema=schema)

        sent_payload = mock_post.call_args[1]["json"]
        self.assertEqual(sent_payload["structured_output_schema"], schema)

    @patch('orchestrator.devin_client.requests.post')
    def test_passes_tags_and_title(self, mock_post):
        self._mock_success(mock_post)

        self.client.create_session("prompt", tags=["triage", "issue-2"], title="Triage: Issue #2")

        sent_payload = mock_post.call_args[1]["json"]
        self.assertEqual(sent_payload["tags"], ["triage", "issue-2"])
        self.assertEqual(sent_payload["title"], "Triage: Issue #2")

    @patch('orchestrator.devin_client.requests.post')
    def test_passes_max_acu_limit(self, mock_post):
        self._mock_success(mock_post)

        self.client.create_session("prompt", max_acu_limit=5)

        sent_payload = mock_post.call_args[1]["json"]
        self.assertEqual(sent_payload["max_acu_limit"], 5)

    @patch('orchestrator.devin_client.requests.post')
    def test_passes_idempotent_flag(self, mock_post):
        self._mock_success(mock_post)

        self.client.create_session("prompt", idempotent=True)

        sent_payload = mock_post.call_args[1]["json"]
        self.assertTrue(sent_payload["idempotent"])

    @patch('orchestrator.devin_client.requests.post')
    def test_passes_playbook_id(self, mock_post):
        self._mock_success(mock_post)

        self.client.create_session("prompt", playbook_id="pb_123")

        sent_payload = mock_post.call_args[1]["json"]
        self.assertEqual(sent_payload["playbook_id"], "pb_123")

    @patch('orchestrator.devin_client.requests.post')
    def test_empty_string_playbook_id_omitted(self, mock_post):
        """An empty string playbook_id (e.g. unset secret) should not be sent."""
        self._mock_success(mock_post)

        self.client.create_session("prompt", playbook_id="")

        sent_payload = mock_post.call_args[1]["json"]
        self.assertNotIn("playbook_id", sent_payload)

    @patch('orchestrator.devin_client.requests.post')
    def test_omits_none_params(self, mock_post):
        """Calling with defaults sends only the prompt — no extra keys."""
        self._mock_success(mock_post)

        self.client.create_session("prompt")

        sent_payload = mock_post.call_args[1]["json"]
        self.assertEqual(sent_payload, {"prompt": "prompt"})
        self.assertNotIn("structured_output_schema", sent_payload)
        self.assertNotIn("tags", sent_payload)
        self.assertNotIn("title", sent_payload)
        self.assertNotIn("max_acu_limit", sent_payload)
        self.assertNotIn("idempotent", sent_payload)
        self.assertNotIn("playbook_id", sent_payload)

    @patch('orchestrator.devin_client.requests.post')
    def test_passes_all_params_together(self, mock_post):
        self._mock_success(mock_post)
        schema = {"type": "object"}

        self.client.create_session(
            "prompt",
            structured_output_schema=schema,
            tags=["fix"],
            title="Fix: #5",
            max_acu_limit=10,
            idempotent=True,
            playbook_id="pb_456",
        )

        sent_payload = mock_post.call_args[1]["json"]
        self.assertEqual(sent_payload["prompt"], "prompt")
        self.assertEqual(sent_payload["structured_output_schema"], schema)
        self.assertEqual(sent_payload["tags"], ["fix"])
        self.assertEqual(sent_payload["title"], "Fix: #5")
        self.assertEqual(sent_payload["max_acu_limit"], 10)
        self.assertTrue(sent_payload["idempotent"])
        self.assertEqual(sent_payload["playbook_id"], "pb_456")
