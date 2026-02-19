"""
Unit tests for orchestrator.pr_nudge — Story 6.

All HTTP calls are mocked; no real GitHub traffic.
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from orchestrator.pr_nudge import (
    PR_NUDGE_MARKER,
    MAX_MATCHES,
    is_fixable,
    _extract_card_from_comment,
    _match_paths,
    _render_nudge_comment,
    nudge_pr,
)
from orchestrator.github_client import DEFAULT_MARKER


# ---------------------------------------------------------------------------
# Card extraction
# ---------------------------------------------------------------------------

class TestExtractCardFromComment(unittest.TestCase):
    """_extract_card_from_comment parses embedded triage JSON."""

    def test_parses_valid_embedded_json(self):
        card_data = {
            "schema_version": "1.0",
            "classification": "bug",
            "confidence": 0.92,
            "summary": "Off-by-one in stats.",
            "affected_paths": ["demo_app/services/stats_service.py"],
        }
        body = (
            "## Triage Card\nSome text\n\n"
            f"<!-- devin-triage:v1\n{json.dumps(card_data)}\n-->"
        )
        result = _extract_card_from_comment(body)
        self.assertIsNotNone(result)
        self.assertEqual(result["classification"], "bug")
        self.assertAlmostEqual(result["confidence"], 0.92)

    def test_returns_none_for_missing_marker(self):
        body = "Just a regular comment with no embedded card."
        self.assertIsNone(_extract_card_from_comment(body))

    def test_returns_none_for_invalid_json(self):
        body = "<!-- devin-triage:v1\n{not valid json\n-->"
        self.assertIsNone(_extract_card_from_comment(body))

    def test_handles_extra_whitespace(self):
        card_data = {"classification": "feature-request", "confidence": 0.8}
        body = f"<!--  devin-triage:v1\n  {json.dumps(card_data)}  \n -->"
        result = _extract_card_from_comment(body)
        self.assertIsNotNone(result)
        self.assertEqual(result["classification"], "feature-request")


# ---------------------------------------------------------------------------
# Path matching
# ---------------------------------------------------------------------------

class TestMatchPaths(unittest.TestCase):
    """_match_paths finds overlapping files between PR and triage cards."""

    def test_exact_match(self):
        pr_files = ["src/app.py", "tests/test_app.py"]
        affected = ["src/app.py"]
        result = _match_paths(pr_files, affected)
        self.assertEqual(result, ["src/app.py"])

    def test_directory_prefix_match(self):
        pr_files = ["demo_app/services/stats_service.py", "README.md"]
        affected = ["demo_app/services/"]
        result = _match_paths(pr_files, affected)
        self.assertEqual(result, ["demo_app/services/stats_service.py"])

    def test_prefix_without_trailing_slash(self):
        """'demo_app/services' should match 'demo_app/services/foo.py'."""
        pr_files = ["demo_app/services/stats_service.py"]
        affected = ["demo_app/services"]
        result = _match_paths(pr_files, affected)
        self.assertEqual(result, ["demo_app/services/stats_service.py"])

    def test_no_match(self):
        pr_files = ["docs/README.md"]
        affected = ["src/app.py"]
        result = _match_paths(pr_files, affected)
        self.assertEqual(result, [])

    def test_no_duplicate_matches(self):
        """A file should appear only once even if multiple affected paths match."""
        pr_files = ["demo_app/services/stats_service.py"]
        affected = ["demo_app/", "demo_app/services/stats_service.py"]
        result = _match_paths(pr_files, affected)
        self.assertEqual(result, ["demo_app/services/stats_service.py"])

    def test_empty_pr_files(self):
        result = _match_paths([], ["src/"])
        self.assertEqual(result, [])

    def test_empty_affected_paths(self):
        result = _match_paths(["src/app.py"], [])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Comment rendering
# ---------------------------------------------------------------------------

class TestRenderNudgeComment(unittest.TestCase):
    """_render_nudge_comment produces Markdown with issue details."""

    def _make_match(self, **overrides):
        base = {
            "issue_number": 1,
            "issue_title": "Bug in stats",
            "classification": "bug",
            "priority": "high",
            "confidence": 0.95,
            "summary": "Off-by-one error.",
            "matched_files": ["demo_app/services/stats_service.py"],
            "fixable": False,
        }
        base.update(overrides)
        return base

    def test_single_match(self):
        body = _render_nudge_comment([self._make_match()])
        self.assertIn("#1: Bug in stats", body)
        self.assertIn("`bug`", body)
        self.assertIn("`high`", body)
        self.assertIn("Off-by-one error.", body)
        self.assertIn(PR_NUDGE_MARKER, body)
        self.assertIn("Consider fixing while you're in this area", body)

    def test_max_matches_truncation(self):
        matches = [self._make_match(issue_number=i) for i in range(1, MAX_MATCHES + 4)]
        body = _render_nudge_comment(matches)
        # Should show MAX_MATCHES issues then a "…and N more" note
        self.assertIn(f"…and **3** more", body)
        # Verify first MAX_MATCHES are present
        for i in range(1, MAX_MATCHES + 1):
            self.assertIn(f"#{i}:", body)
        # 6, 7, 8 should NOT have headers (truncated)
        self.assertNotIn(f"### #{MAX_MATCHES + 1}:", body)

    def test_exactly_max_matches_no_truncation_note(self):
        matches = [self._make_match(issue_number=i) for i in range(1, MAX_MATCHES + 1)]
        body = _render_nudge_comment(matches)
        self.assertNotIn("…and", body)

    def test_marker_present(self):
        body = _render_nudge_comment([self._make_match()])
        self.assertIn(PR_NUDGE_MARKER, body)

    def test_fixable_match_shows_checkbox(self):
        body = _render_nudge_comment([self._make_match(fixable=True)])
        self.assertIn("- [ ] **Attempt auto-fix for #1** with Devin", body)

    def test_non_fixable_match_hides_checkbox(self):
        body = _render_nudge_comment([self._make_match(fixable=False)])
        self.assertNotIn("Attempt auto-fix", body)

    def test_mixed_fixable_and_not(self):
        matches = [
            self._make_match(issue_number=1, fixable=True),
            self._make_match(issue_number=2, fixable=False),
            self._make_match(issue_number=3, fixable=True),
        ]
        body = _render_nudge_comment(matches)
        self.assertIn("- [ ] **Attempt auto-fix for #1** with Devin", body)
        self.assertNotIn("Attempt auto-fix for #2", body)
        self.assertIn("- [ ] **Attempt auto-fix for #3** with Devin", body)


# ---------------------------------------------------------------------------
# is_fixable gate
# ---------------------------------------------------------------------------

class TestIsFixable(unittest.TestCase):
    """is_fixable decides whether a triage card qualifies for the auto-fix checkbox."""

    def _make_card(self, **overrides):
        base = {
            "classification": "bug",
            "confidence": 0.92,
            "questions": [],
        }
        base.update(overrides)
        return base

    def test_clear_bug_high_confidence(self):
        self.assertTrue(is_fixable(self._make_card()))

    def test_unclear_not_fixable(self):
        self.assertFalse(is_fixable(self._make_card(classification="unclear")))

    def test_bug_with_questions_not_fixable(self):
        self.assertFalse(is_fixable(self._make_card(questions=["Repro steps?"])))

    def test_low_confidence_not_fixable(self):
        self.assertFalse(is_fixable(self._make_card(confidence=0.69)))

    def test_exactly_0_7_is_fixable(self):
        self.assertTrue(is_fixable(self._make_card(confidence=0.7)))

    def test_feature_request_not_fixable(self):
        self.assertFalse(is_fixable(self._make_card(classification="feature-request")))

    def test_question_not_fixable(self):
        self.assertFalse(is_fixable(self._make_card(classification="question")))


# ---------------------------------------------------------------------------
# End-to-end nudge_pr flow
# ---------------------------------------------------------------------------

class TestNudgePr(unittest.TestCase):
    """nudge_pr orchestrates the full flow with mocked GitHubClient."""

    def _build_triage_comment(self, card: dict) -> str:
        return (
            f"{DEFAULT_MARKER}\n\n## Triage Card\n\n"
            f"<!-- devin-triage:v1\n{json.dumps(card)}\n-->"
        )

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_posts_nudge_when_match_found(self, MockGH):
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = ["demo_app/services/stats_service.py"]
        gh.list_issues.return_value = [
            {"number": 2, "title": "Off-by-one in stats"},
        ]
        card = {
            "classification": "bug",
            "confidence": 0.95,
            "summary": "Off by one.",
            "affected_paths": ["demo_app/services/stats_service.py"],
            "suggested_priority": "high",
        }
        gh.get_issue_comments.return_value = [
            {"body": self._build_triage_comment(card)},
        ]

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_called_once()
        call_args = gh.upsert_comment.call_args
        self.assertEqual(call_args[0][0], "owner/repo")
        self.assertEqual(call_args[0][1], 10)
        self.assertEqual(call_args[0][2], PR_NUDGE_MARKER)
        self.assertIn("#2: Off-by-one in stats", call_args[0][3])

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_silent_when_no_matches(self, MockGH):
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = ["docs/README.md"]
        gh.list_issues.return_value = [
            {"number": 2, "title": "Bug in stats"},
        ]
        card = {
            "classification": "bug",
            "confidence": 0.9,
            "summary": "Stats bug.",
            "affected_paths": ["demo_app/services/stats_service.py"],
            "suggested_priority": "medium",
        }
        gh.get_issue_comments.return_value = [
            {"body": self._build_triage_comment(card)},
        ]

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_not_called()

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_silent_when_no_triaged_issues(self, MockGH):
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = ["src/app.py"]
        gh.list_issues.return_value = []

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_not_called()

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_silent_when_no_changed_files(self, MockGH):
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = []

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.list_issues.assert_not_called()
        gh.upsert_comment.assert_not_called()

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_skips_issue_without_triage_card(self, MockGH):
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = ["demo_app/services/stats_service.py"]
        gh.list_issues.return_value = [
            {"number": 2, "title": "No card issue"},
        ]
        # Comment without the triage marker
        gh.get_issue_comments.return_value = [
            {"body": "Regular human comment."},
        ]

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_not_called()

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_skips_issue_with_empty_affected_paths(self, MockGH):
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = ["demo_app/services/stats_service.py"]
        gh.list_issues.return_value = [
            {"number": 2, "title": "No paths issue"},
        ]
        card = {
            "classification": "question",
            "confidence": 0.5,
            "summary": "A vague question.",
            "affected_paths": [],
            "suggested_priority": "low",
        }
        gh.get_issue_comments.return_value = [
            {"body": self._build_triage_comment(card)},
        ]

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_not_called()

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_multiple_issues_matched(self, MockGH):
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = [
            "demo_app/services/stats_service.py",
            "demo_app/services/ledger_service.py",
        ]
        card1 = {
            "classification": "bug",
            "confidence": 0.95,
            "summary": "Off-by-one.",
            "affected_paths": ["demo_app/services/stats_service.py"],
            "suggested_priority": "high",
        }
        card2 = {
            "classification": "bug",
            "confidence": 0.90,
            "summary": "Sorting issue.",
            "affected_paths": ["demo_app/services/ledger_service.py"],
            "suggested_priority": "medium",
        }
        gh.list_issues.return_value = [
            {"number": 2, "title": "Stats bug"},
            {"number": 3, "title": "Sorting bug"},
        ]
        gh.get_issue_comments.side_effect = [
            [{"body": self._build_triage_comment(card1)}],
            [{"body": self._build_triage_comment(card2)}],
        ]

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_called_once()
        body = gh.upsert_comment.call_args[0][3]
        self.assertIn("#2: Stats bug", body)
        self.assertIn("#3: Sorting bug", body)

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_fixable_bug_gets_checkbox_in_nudge(self, MockGH):
        """A high-confidence bug with no questions gets an auto-fix checkbox."""
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = ["demo_app/services/stats_service.py"]
        gh.list_issues.return_value = [
            {"number": 2, "title": "Off-by-one"},
        ]
        card = {
            "classification": "bug",
            "confidence": 0.95,
            "summary": "Off by one.",
            "affected_paths": ["demo_app/services/stats_service.py"],
            "suggested_priority": "high",
            "questions": [],
        }
        gh.get_issue_comments.return_value = [
            {"body": self._build_triage_comment(card)},
        ]

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_called_once()
        body = gh.upsert_comment.call_args[0][3]
        self.assertIn("- [ ] **Attempt auto-fix for #2** with Devin", body)

    @patch("orchestrator.pr_nudge.GitHubClient")
    def test_unclear_issue_no_checkbox_in_nudge(self, MockGH):
        """An unclear issue with questions should NOT get an auto-fix checkbox."""
        gh = MockGH.return_value
        gh.get_pr_changed_files.return_value = ["demo_app/services/stats_service.py"]
        gh.list_issues.return_value = [
            {"number": 3, "title": "Something weird"},
        ]
        card = {
            "classification": "unclear",
            "confidence": 0.4,
            "summary": "Vague description.",
            "affected_paths": ["demo_app/services/stats_service.py"],
            "suggested_priority": "low",
            "questions": ["What exactly happened?"],
        }
        gh.get_issue_comments.return_value = [
            {"body": self._build_triage_comment(card)},
        ]

        nudge_pr(repo="owner/repo", pr_number=10)

        gh.upsert_comment.assert_called_once()
        body = gh.upsert_comment.call_args[0][3]
        self.assertNotIn("Attempt auto-fix", body)


if __name__ == "__main__":
    unittest.main()
