"""Tests for scripts/upload_playbooks.py"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# The script lives outside orchestrator/, so import it directly.
import importlib
import sys


def _import_upload():
    """Import the upload module from scripts/."""
    spec = importlib.util.spec_from_file_location(
        "upload_playbooks",
        Path(__file__).resolve().parent.parent.parent / "scripts" / "upload_playbooks.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCreatePlaybook(unittest.TestCase):

    @patch.dict("os.environ", {"DEVIN_API_KEY": "apk_test"})
    @patch("requests.post")
    def test_create_playbook_returns_id(self, mock_post):
        mod = _import_upload()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"playbook_id": "pb_new123"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        pid = mod.create_playbook("Test Title", "# Body")

        self.assertEqual(pid, "pb_new123")
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1]["json"]
        self.assertEqual(payload["title"], "Test Title")
        self.assertEqual(payload["body"], "# Body")


class TestUpdatePlaybook(unittest.TestCase):

    @patch.dict("os.environ", {"DEVIN_API_KEY": "apk_test"})
    @patch("requests.put")
    def test_update_playbook_calls_put(self, mock_put):
        mod = _import_upload()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_put.return_value = mock_resp

        mod.update_playbook("pb_exist", "Updated", "# New body")

        mock_put.assert_called_once()
        url = mock_put.call_args[0][0] if mock_put.call_args[0] else mock_put.call_args.kwargs["url"]
        self.assertIn("pb_exist", url)


class TestPlaybookFilesExist(unittest.TestCase):
    """Ensure the markdown playbook files are present and non-empty."""

    def test_triage_playbook_exists(self):
        mod = _import_upload()
        path = mod.PLAYBOOKS["triage"]["file"]
        self.assertTrue(path.exists(), f"Missing: {path}")
        self.assertGreater(path.stat().st_size, 50)

    def test_fix_playbook_exists(self):
        mod = _import_upload()
        path = mod.PLAYBOOKS["fix"]["file"]
        self.assertTrue(path.exists(), f"Missing: {path}")
        self.assertGreater(path.stat().st_size, 50)


if __name__ == "__main__":
    unittest.main()
