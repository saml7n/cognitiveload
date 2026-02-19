"""
GitHub API helpers for idempotent comment management and label operations.

Story 4: Standalone module — no workflows, no orchestration logic.
"""

import os
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Default marker embedded in bot comments for idempotent upsert.
DEFAULT_MARKER = "<!-- devin-triage:v1 -->"


class GitHubClient:
    """Thin wrapper around the GitHub REST API for issue/PR operations."""

    def __init__(self, token: Optional[str] = None, base_url: str = "https://api.github.com"):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN is required")

        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    # ------------------------------------------------------------------
    # Comment helpers
    # ------------------------------------------------------------------

    def find_bot_comment(
        self, repo: str, issue_number: int, marker: str = DEFAULT_MARKER
    ) -> Optional[int]:
        """Return the comment ID whose body contains *marker*, or None."""
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
        page = 1
        while True:
            resp = self._session.get(url, params={"per_page": 100, "page": page})
            resp.raise_for_status()
            comments = resp.json()
            if not comments:
                break
            for comment in comments:
                if marker in comment.get("body", ""):
                    return comment["id"]
            page += 1
        return None

    def upsert_comment(
        self,
        repo: str,
        issue_number: int,
        marker: str,
        body: str,
    ) -> None:
        """Create or update the single bot comment identified by *marker*.

        The marker is prepended to the body if not already present so that
        future calls to ``find_bot_comment`` can locate it.
        """
        if marker not in body:
            body = f"{marker}\n\n{body}"

        existing_id = self.find_bot_comment(repo, issue_number, marker)

        if existing_id is not None:
            url = f"{self.base_url}/repos/{repo}/issues/comments/{existing_id}"
            resp = self._session.patch(url, json={"body": body})
        else:
            url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
            resp = self._session.post(url, json={"body": body})

        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Label helpers
    # ------------------------------------------------------------------

    def add_labels(
        self, repo: str, issue_number: int, labels: list[str]
    ) -> None:
        """Add *labels* to an issue/PR without removing existing ones."""
        if not labels:
            return
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/labels"
        resp = self._session.post(url, json={"labels": labels})
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Issue helpers
    # ------------------------------------------------------------------

    def list_issues(
        self, repo: str, labels: list[str], state: str = "open"
    ) -> list[dict]:
        """Return issues matching *labels* (AND logic) and *state*."""
        url = f"{self.base_url}/repos/{repo}/issues"
        issues: list[dict] = []
        page = 1
        while True:
            resp = self._session.get(
                url,
                params={
                    "labels": ",".join(labels),
                    "state": state,
                    "per_page": 100,
                    "page": page,
                },
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            # GitHub's /issues endpoint also returns PRs; filter them out.
            issues.extend(i for i in batch if "pull_request" not in i)
            page += 1
        return issues

    def get_issue_comments(
        self, repo: str, issue_number: int
    ) -> list[dict]:
        """Return all comments on an issue."""
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
        comments: list[dict] = []
        page = 1
        while True:
            resp = self._session.get(url, params={"per_page": 100, "page": page})
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            comments.extend(batch)
            page += 1
        return comments

    # ------------------------------------------------------------------
    # PR helpers
    # ------------------------------------------------------------------

    def get_pr_changed_files(self, repo: str, pr_number: int) -> list[str]:
        """Return a list of file paths changed in the given PR."""
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/files"
        files: list[str] = []
        page = 1
        while True:
            resp = self._session.get(url, params={"per_page": 100, "page": page})
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            files.extend(f["filename"] for f in batch)
            page += 1
        return files
