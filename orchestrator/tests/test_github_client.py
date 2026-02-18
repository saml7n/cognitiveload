"""
Unit tests for orchestrator.github_client — Story 4.

All HTTP calls are mocked via ``unittest.mock``; no real GitHub traffic.
"""

import unittest
from unittest.mock import MagicMock, patch, call

from orchestrator.github_client import GitHubClient, DEFAULT_MARKER


def _ok_response(json_data=None, status_code=200):
    """Return a mock Response whose .json() and .raise_for_status() behave."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.raise_for_status.return_value = None
    return resp


class TestFindBotComment(unittest.TestCase):
    """find_bot_comment searches paginated comments for the marker."""

    def setUp(self):
        self.client = GitHubClient(token="test-token")

    def test_found_on_first_page(self):
        comments = [
            {"id": 10, "body": "unrelated comment"},
            {"id": 42, "body": f"triaged {DEFAULT_MARKER} details"},
        ]
        self.client._session = MagicMock()
        self.client._session.get.return_value = _ok_response(comments)

        result = self.client.find_bot_comment("owner/repo", 7)
        self.assertEqual(result, 42)

    def test_not_found(self):
        self.client._session = MagicMock()
        self.client._session.get.return_value = _ok_response([])

        result = self.client.find_bot_comment("owner/repo", 7)
        self.assertIsNone(result)


class TestUpsertComment(unittest.TestCase):
    """upsert_comment creates when absent, updates when present."""

    def setUp(self):
        self.client = GitHubClient(token="test-token")
        self.client._session = MagicMock()
        self.marker = DEFAULT_MARKER
        self.repo = "owner/repo"
        self.issue = 5

    def test_creates_when_no_prior_comment(self):
        # find_bot_comment returns None → POST to create
        self.client._session.get.return_value = _ok_response([])  # no comments
        self.client._session.post.return_value = _ok_response(status_code=201)

        self.client.upsert_comment(self.repo, self.issue, self.marker, "New triage card")

        # Verify POST was called (create path)
        post_call = self.client._session.post.call_args
        self.assertIn(f"/repos/{self.repo}/issues/{self.issue}/comments", post_call[0][0])
        body_sent = post_call[1]["json"]["body"]
        self.assertIn(self.marker, body_sent)
        self.assertIn("New triage card", body_sent)

    def test_updates_when_prior_comment_exists(self):
        existing = [{"id": 99, "body": f"{self.marker}\nold content"}]
        self.client._session.get.return_value = _ok_response(existing)
        self.client._session.patch.return_value = _ok_response()

        self.client.upsert_comment(self.repo, self.issue, self.marker, "Updated card")

        # Verify PATCH was called (update path)
        patch_call = self.client._session.patch.call_args
        self.assertIn("/repos/owner/repo/issues/comments/99", patch_call[0][0])
        body_sent = patch_call[1]["json"]["body"]
        self.assertIn(self.marker, body_sent)
        self.assertIn("Updated card", body_sent)

    def test_marker_prepended_when_missing_from_body(self):
        self.client._session.get.return_value = _ok_response([])
        self.client._session.post.return_value = _ok_response(status_code=201)

        self.client.upsert_comment(self.repo, self.issue, self.marker, "plain body")

        body_sent = self.client._session.post.call_args[1]["json"]["body"]
        self.assertTrue(body_sent.startswith(self.marker))

    def test_marker_not_duplicated_when_already_in_body(self):
        self.client._session.get.return_value = _ok_response([])
        self.client._session.post.return_value = _ok_response(status_code=201)

        body_with_marker = f"{self.marker}\nmy content"
        self.client.upsert_comment(self.repo, self.issue, self.marker, body_with_marker)

        body_sent = self.client._session.post.call_args[1]["json"]["body"]
        self.assertEqual(body_sent.count(self.marker), 1)


class TestAddLabels(unittest.TestCase):
    """add_labels POSTs without removing existing labels."""

    def setUp(self):
        self.client = GitHubClient(token="test-token")
        self.client._session = MagicMock()

    def test_adds_labels(self):
        self.client._session.post.return_value = _ok_response(
            [{"name": "bug"}, {"name": "devin:triaged"}]
        )

        self.client.add_labels("owner/repo", 3, ["bug", "devin:triaged"])

        post_call = self.client._session.post.call_args
        self.assertIn("/repos/owner/repo/issues/3/labels", post_call[0][0])
        self.assertEqual(post_call[1]["json"]["labels"], ["bug", "devin:triaged"])

    def test_empty_list_is_noop(self):
        self.client.add_labels("owner/repo", 3, [])
        self.client._session.post.assert_not_called()


class TestGetPrChangedFiles(unittest.TestCase):
    """get_pr_changed_files returns filenames across pages."""

    def setUp(self):
        self.client = GitHubClient(token="test-token")
        self.client._session = MagicMock()

    def test_single_page(self):
        files = [{"filename": "src/app.py"}, {"filename": "tests/test_app.py"}]
        self.client._session.get.side_effect = [
            _ok_response(files),
            _ok_response([]),  # second page empty → stop
        ]

        result = self.client.get_pr_changed_files("owner/repo", 12)
        self.assertEqual(result, ["src/app.py", "tests/test_app.py"])

    def test_multi_page(self):
        page1 = [{"filename": "a.py"}]
        page2 = [{"filename": "b.py"}]
        self.client._session.get.side_effect = [
            _ok_response(page1),
            _ok_response(page2),
            _ok_response([]),
        ]

        result = self.client.get_pr_changed_files("owner/repo", 12)
        self.assertEqual(result, ["a.py", "b.py"])
