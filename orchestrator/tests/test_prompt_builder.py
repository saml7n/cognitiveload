"""
Unit tests for orchestrator.prompt_builder.
"""

import json
import unittest

from orchestrator.prompt_builder import build_triage_prompt


class TestBuildTriagePrompt(unittest.TestCase):

    def test_contains_issue_metadata(self):
        prompt = build_triage_prompt(
            repo="owner/repo",
            issue_number=42,
            issue_title="App crashes on login",
            issue_body="When I click login the page goes blank.",
        )
        self.assertIn("owner/repo", prompt)
        self.assertIn("#42", prompt)
        self.assertIn("App crashes on login", prompt)
        self.assertIn("When I click login the page goes blank.", prompt)

    def test_contains_schema(self):
        prompt = build_triage_prompt(
            repo="owner/repo",
            issue_number=1,
            issue_title="Test",
            issue_body="Body",
        )
        # The schema should be embedded so Devin knows the output format
        self.assertIn('"schema_version"', prompt)
        self.assertIn('"classification"', prompt)
        self.assertIn('"suggested_priority"', prompt)

    def test_output_instructions(self):
        prompt = build_triage_prompt(
            repo="owner/repo",
            issue_number=1,
            issue_title="Test",
            issue_body="Body",
        )
        self.assertIn("Return **only** a single JSON object", prompt)
        self.assertIn("v1", prompt)

    def test_playbook_active_compact_prompt(self):
        prompt = build_triage_prompt(
            repo="owner/repo",
            issue_number=42,
            issue_title="Bug",
            issue_body="Desc",
            playbook_active=True,
        )
        # Should still contain issue context
        self.assertIn("owner/repo", prompt)
        self.assertIn("#42", prompt)
        self.assertIn("Bug", prompt)
        # Should NOT contain the full inline schema dump
        self.assertNotIn('"$schema"', prompt)
        # Should reference the playbook
        self.assertIn("playbook", prompt)
        # Should be significantly shorter than the non-playbook version
        full_prompt = build_triage_prompt(
            repo="owner/repo",
            issue_number=42,
            issue_title="Bug",
            issue_body="Desc",
            playbook_active=False,
        )
        self.assertLess(len(prompt), len(full_prompt) * 0.6)

    def test_playbook_active_mentions_relative_paths(self):
        prompt = build_triage_prompt(
            repo="owner/repo",
            issue_number=1,
            issue_title="X",
            issue_body="Y",
            playbook_active=True,
        )
        self.assertIn("repo-relative", prompt)

    def test_no_playbook_mentions_relative_paths(self):
        prompt = build_triage_prompt(
            repo="owner/repo",
            issue_number=1,
            issue_title="X",
            issue_body="Y",
            playbook_active=False,
        )
        self.assertIn("repo-relative", prompt)
