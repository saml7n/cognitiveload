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
