"""
Unit tests for orchestrator.triage — Story 5.

All external calls (Devin, GitHub) are mocked.
"""

import json
import unittest
from unittest.mock import MagicMock, patch, call

from orchestrator.triage import triage_issue, _extract_triage_card, _render_comment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_CARD = {
    "schema_version": "v1",
    "classification": "bug",
    "confidence": 0.92,
    "summary": "Off-by-one in /summary endpoint.",
    "questions": [],
    "affected_paths": ["demo_app/services/stats_service.py"],
    "suggested_labels": ["bug"],
    "suggested_priority": "medium",
}

UNCLEAR_CARD = {
    "schema_version": "v1",
    "classification": "unclear",
    "confidence": 0.40,
    "summary": "Issue description is too vague to triage.",
    "questions": [
        "What version of the app are you running?",
        "Can you share the exact error message?",
    ],
    "affected_paths": [],
    "suggested_labels": [],
    "suggested_priority": "low",
}


# ---------------------------------------------------------------------------
# _extract_triage_card
# ---------------------------------------------------------------------------


class TestExtractTriageCard(unittest.TestCase):
    """Verify we can pull a triage card from various Devin response shapes."""

    def test_from_structured_output(self):
        session_data = {"structured_output": VALID_CARD, "messages": []}
        card = _extract_triage_card(session_data)
        self.assertEqual(card["classification"], "bug")

    def test_from_messages_json(self):
        session_data = {
            "structured_output": None,
            "messages": [
                {"message": "Let me investigate..."},
                {"message": json.dumps(VALID_CARD)},
            ],
        }
        card = _extract_triage_card(session_data)
        self.assertIsNotNone(card)
        self.assertEqual(card["classification"], "bug")

    def test_from_messages_json_fenced(self):
        fenced = f"Here is the triage:\n```json\n{json.dumps(VALID_CARD)}\n```"
        session_data = {
            "structured_output": None,
            "messages": [{"message": fenced}],
        }
        card = _extract_triage_card(session_data)
        self.assertIsNotNone(card)
        self.assertEqual(card["summary"], VALID_CARD["summary"])

    def test_returns_none_when_no_valid_json(self):
        session_data = {
            "structured_output": None,
            "messages": [
                {"message": "I couldn't figure it out."},
            ],
        }
        card = _extract_triage_card(session_data)
        self.assertIsNone(card)

    def test_from_messages_json_embedded_in_prose(self):
        """Devin often wraps the JSON in explanatory text without fences."""
        prose = (
            "Investigating the issue now — I'll look at the codebase "
            "and get back to you with a triage card.\n\n"
            + json.dumps(VALID_CARD)
        )
        session_data = {
            "structured_output": None,
            "messages": [
                {"message": "Let me investigate..."},
                {"message": prose},
            ],
        }
        card = _extract_triage_card(session_data)
        self.assertIsNotNone(card)
        self.assertEqual(card["classification"], "bug")


# ---------------------------------------------------------------------------
# _render_comment
# ---------------------------------------------------------------------------


class TestRenderComment(unittest.TestCase):

    def test_contains_marker(self):
        body = _render_comment(VALID_CARD)
        self.assertIn("<!-- devin-triage:v1", body)

    def test_contains_summary(self):
        body = _render_comment(VALID_CARD)
        self.assertIn("Off-by-one", body)

    def test_contains_questions_when_present(self):
        body = _render_comment(UNCLEAR_CARD)
        self.assertIn("Clarification Questions", body)
        self.assertIn("What version of the app", body)

    def test_no_questions_section_when_empty(self):
        body = _render_comment(VALID_CARD)
        self.assertNotIn("Clarification Questions", body)

    def test_embedded_json_is_valid(self):
        body = _render_comment(VALID_CARD)
        # Extract the JSON from the HTML comment
        start = body.index("<!-- devin-triage:v1\n") + len("<!-- devin-triage:v1\n")
        end = body.index("\n-->")
        embedded_json = body[start:end]
        parsed = json.loads(embedded_json)
        self.assertEqual(parsed["classification"], "bug")

    def test_no_checkbox_in_triage_comment(self):
        """Triage comment is purely informational — no auto-fix checkbox."""
        body = _render_comment(VALID_CARD)
        self.assertNotIn("Attempt auto-fix", body)
        self.assertNotIn("[ ]", body)
        self.assertNotIn("[x]", body)



# ---------------------------------------------------------------------------
# triage_issue (end-to-end, mocked)
# ---------------------------------------------------------------------------


class TestTriageIssue(unittest.TestCase):
    """Full flow with mocked Devin and GitHub clients."""

    @patch("orchestrator.triage.GitHubClient")
    @patch("orchestrator.triage.DevinClient")
    def test_clear_issue_gets_triaged_label(self, MockDevin, MockGH):
        devin_instance = MockDevin.return_value
        devin_instance.create_session.return_value = "sess-123"
        devin_instance.poll_session.return_value = {
            "status_enum": "finished",
            "structured_output": VALID_CARD,
            "messages": [],
        }

        gh_instance = MockGH.return_value

        triage_issue(
            repo="owner/repo",
            issue_number=10,
            issue_title="Bug in stats",
            issue_body="The /summary endpoint returns wrong count.",
        )

        # Verify comment was posted
        gh_instance.upsert_comment.assert_called_once()
        comment_body = gh_instance.upsert_comment.call_args[0][2]  # 3rd positional arg = marker
        # Actually let's check the kwargs/args more carefully
        args = gh_instance.upsert_comment.call_args
        self.assertEqual(args[0][0], "owner/repo")
        self.assertEqual(args[0][1], 10)

        # Verify labels include devin:triaged (clear issue, no questions)
        gh_instance.add_labels.assert_called_once()
        labels = gh_instance.add_labels.call_args[0][2]
        self.assertIn("devin:triaged", labels)
        self.assertNotIn("needs-info", labels)

    @patch("orchestrator.triage.GitHubClient")
    @patch("orchestrator.triage.DevinClient")
    def test_unclear_issue_gets_needs_info_label(self, MockDevin, MockGH):
        devin_instance = MockDevin.return_value
        devin_instance.create_session.return_value = "sess-456"
        devin_instance.poll_session.return_value = {
            "status_enum": "finished",
            "structured_output": UNCLEAR_CARD,
            "messages": [],
        }

        gh_instance = MockGH.return_value

        triage_issue(
            repo="owner/repo",
            issue_number=11,
            issue_title="Something is broken",
            issue_body="It doesn't work.",
        )

        # Verify labels include needs-info
        gh_instance.add_labels.assert_called_once()
        labels = gh_instance.add_labels.call_args[0][2]
        self.assertIn("needs-info", labels)
        self.assertNotIn("devin:triaged", labels)

    @patch("orchestrator.triage.GitHubClient")
    @patch("orchestrator.triage.DevinClient")
    def test_fallback_when_no_valid_card(self, MockDevin, MockGH):
        devin_instance = MockDevin.return_value
        devin_instance.create_session.return_value = "sess-789"
        devin_instance.poll_session.return_value = {
            "status_enum": "finished",
            "structured_output": None,
            "messages": [{"message": "I'm confused."}],
        }

        gh_instance = MockGH.return_value

        triage_issue(
            repo="owner/repo",
            issue_number=12,
            issue_title="???",
            issue_body="",
        )

        # Fallback: posts a warning comment and adds needs-info
        gh_instance.upsert_comment.assert_called_once()
        body = gh_instance.upsert_comment.call_args[0][3]
        self.assertIn("unable to produce a valid triage card", body)

        gh_instance.add_labels.assert_called_once()
        labels = gh_instance.add_labels.call_args[0][2]
        self.assertIn("needs-info", labels)

    @patch("orchestrator.triage.GitHubClient")
    @patch("orchestrator.triage.DevinClient")
    def test_idempotent_marker_in_comment(self, MockDevin, MockGH):
        """The comment must contain the marker for idempotent upsert."""
        devin_instance = MockDevin.return_value
        devin_instance.create_session.return_value = "sess-abc"
        devin_instance.poll_session.return_value = {
            "status_enum": "finished",
            "structured_output": VALID_CARD,
            "messages": [],
        }

        gh_instance = MockGH.return_value

        triage_issue(
            repo="owner/repo",
            issue_number=13,
            issue_title="Test",
            issue_body="Test body",
        )

        # The upsert_comment call includes the DEFAULT_MARKER
        from orchestrator.github_client import DEFAULT_MARKER
        marker_arg = gh_instance.upsert_comment.call_args[0][2]
        self.assertEqual(marker_arg, DEFAULT_MARKER)

    @patch("orchestrator.triage.GitHubClient")
    @patch("orchestrator.triage.DevinClient")
    def test_triage_passes_structured_output_schema(self, MockDevin, MockGH):
        """create_session must receive the triage card JSON Schema."""
        devin_instance = MockDevin.return_value
        devin_instance.create_session.return_value = "sess-schema"
        devin_instance.poll_session.return_value = {
            "status_enum": "finished",
            "structured_output": VALID_CARD,
            "messages": [],
        }
        MockGH.return_value  # not inspected here

        triage_issue(
            repo="owner/repo",
            issue_number=14,
            issue_title="Schema test",
            issue_body="Body",
        )

        call_kwargs = devin_instance.create_session.call_args
        # structured_output_schema should be a dict with JSON Schema keys
        schema = call_kwargs[1].get("structured_output_schema") if call_kwargs[1] else None
        if schema is None:
            # May be passed as keyword via kwargs
            schema = call_kwargs.kwargs.get("structured_output_schema")
        self.assertIsNotNone(schema, "structured_output_schema not passed to create_session")
        self.assertEqual(schema.get("title"), "TriageCard")
        self.assertIn("classification", schema.get("properties", {}))
