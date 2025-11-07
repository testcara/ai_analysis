"""
GitHub API client for fetching PR data and metrics.
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from ai_impact_analysis.utils.logger import logger


class GitHubClient:
    """Client for interacting with GitHub API to fetch PR data."""

    # List of bot usernames to exclude from human metrics
    BOT_USERS = {
        "coderabbit",
        "coderabbitai",
        "coderabbit[bot]",
        "dependabot",
        "dependabot[bot]",
        "renovate",
        "renovate[bot]",
        "github-actions",
        "github-actions[bot]",
        "red-hat-konflux",
        "red-hat-konflux[bot]",
    }

    def __init__(
        self,
        token: Optional[str] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
    ):
        """
        Initialize GitHub API client.

        Args:
            token: GitHub personal access token (or use GITHUB_TOKEN env var)
            repo_owner: Repository owner/organization (or use GITHUB_REPO_OWNER env var)
            repo_name: Repository name (or use GITHUB_REPO_NAME env var)
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo_owner = repo_owner or os.getenv("GITHUB_REPO_OWNER")
        self.repo_name = repo_name or os.getenv("GITHUB_REPO_NAME")

        if not self.token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable or pass token parameter."
            )

        if not self.repo_owner or not self.repo_name:
            raise ValueError(
                "Repository owner and name are required. Set GITHUB_REPO_OWNER and GITHUB_REPO_NAME environment variables."
            )

        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        logger.info(f"GitHub client initialized for {self.repo_owner}/{self.repo_name}")

    @staticmethod
    def is_bot_user(username: str) -> bool:
        """
        Check if a username belongs to a bot.

        Args:
            username: GitHub username to check

        Returns:
            True if the username is a bot, False otherwise
        """
        if not username:
            return False
        return username.lower() in GitHubClient.BOT_USERS or username.lower().endswith("[bot]")

    def fetch_merged_prs(
        self, start_date: str, end_date: str, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch all merged PRs within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            per_page: Results per page (max 100)

        Returns:
            List of PR dictionaries
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"

        all_prs = []
        page = 1

        while True:
            params = {
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": per_page,
                "page": page,
            }

            logger.debug(f"Fetching PRs page {page}...")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            prs = response.json()

            if not prs:
                break

            # Filter merged PRs within date range, excluding bot-authored PRs
            for pr in prs:
                if not pr.get("merged_at"):
                    continue

                # Skip PRs created by bots
                author = pr.get("user", {}).get("login", "")
                if self.is_bot_user(author):
                    logger.debug(f"Skipping bot-authored PR #{pr.get('number')} by {author}")
                    continue

                merged_date = datetime.strptime(pr["merged_at"], "%Y-%m-%dT%H:%M:%SZ")
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

                if start <= merged_date < end:
                    all_prs.append(pr)
                elif merged_date < start:
                    # Since we're sorting by updated desc, if we hit a PR merged before start_date,
                    # we might still need to continue because PRs can be updated after merge
                    pass

            # Check if we should continue
            # If the oldest PR in this page was updated before start_date, we can stop
            oldest_updated = min(
                datetime.strptime(pr["updated_at"], "%Y-%m-%dT%H:%M:%SZ") for pr in prs
            )
            if oldest_updated < start:
                break

            page += 1

        logger.info(f"Fetched {len(all_prs)} merged PRs between {start_date} and {end_date}")
        return all_prs

    def get_pr_details(self, pr_number: int) -> Dict[str, Any]:
        """
        Get full details for a specific PR including diff statistics.

        Args:
            pr_number: PR number

        Returns:
            PR dictionary with full details
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_pr_commits(self, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get all commits for a specific PR.

        Args:
            pr_number: PR number

        Returns:
            List of commit dictionaries
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/commits"

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_pr_reviews(self, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get all reviews for a specific PR.

        Args:
            pr_number: PR number

        Returns:
            List of review dictionaries
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/reviews"

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def get_pr_comments(
        self, pr_number: int, reviews: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Get all review comments for a specific PR.

        Args:
            pr_number: PR number
            reviews: Optional pre-fetched reviews list (to avoid duplicate API call)

        Returns:
            Dict with review_comments, issue_comments, and approval_reviews
        """
        # Get review comments (inline comments on code)
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/comments"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        review_comments = response.json()

        # Get issue comments (general PR discussion)
        url = (
            f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues/{pr_number}/comments"
        )
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        issue_comments = response.json()

        # Use provided reviews or fetch if not provided
        if reviews is None:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/reviews"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            reviews = response.json()

        # Identify approval reviews (APPROVED state with minimal or no substantive comment)
        approval_review_ids = set()
        for review in reviews:
            if review.get("state") == "APPROVED":
                body = review.get("body", "").strip()
                # Consider it an approval-only comment if body is empty or very short (< 10 chars)
                # or contains only common approval phrases
                if (
                    not body
                    or len(body) < 10
                    or body.lower() in ["lgtm", "approved", "approve", "👍", ":+1:", "looks good"]
                ):
                    approval_review_ids.add(review.get("id"))

        return {
            "review_comments": review_comments,
            "issue_comments": issue_comments,
            "total_comments": len(review_comments) + len(issue_comments),
            "approval_review_ids": approval_review_ids,
        }

    def detect_ai_assistance(self, pr_number: int) -> Dict[str, Any]:
        """
        Detect AI assistance by examining commit messages for "Assisted-by" trailers.

        Args:
            pr_number: PR number

        Returns:
            Dict with AI assistance information:
            {
                'has_ai_assistance': bool,
                'ai_tools': List[str],  # e.g., ['Claude', 'Cursor']
                'ai_commits_count': int,
                'total_commits': int,
                'ai_percentage': float
            }
        """
        commits = self.get_pr_commits(pr_number)

        ai_tools = set()
        ai_commits = 0

        for commit in commits:
            message = commit["commit"]["message"]

            # Check for "Assisted-by" trailer
            if "Assisted-by: Claude" in message or "assisted-by: claude" in message.lower():
                ai_tools.add("Claude")
                ai_commits += 1

            if "Assisted-by: Cursor" in message or "assisted-by: cursor" in message.lower():
                ai_tools.add("Cursor")
                ai_commits += 1

            # Also check for Co-Authored-By patterns
            if "Co-Authored-By: Claude" in message:
                ai_tools.add("Claude")
                ai_commits += 1

        total_commits = len(commits)

        return {
            "has_ai_assistance": len(ai_tools) > 0,
            "ai_tools": sorted(list(ai_tools)),
            "ai_commits_count": ai_commits,
            "total_commits": total_commits,
            "ai_percentage": (ai_commits / total_commits * 100) if total_commits > 0 else 0,
        }

    def get_pr_detailed_metrics(self, pr: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed metrics for a single PR.

        Args:
            pr: PR dictionary from GitHub API

        Returns:
            Dictionary with detailed metrics
        """
        pr_number = pr["number"]

        # Get full PR details to ensure we have diff statistics
        pr_full = self.get_pr_details(pr_number)

        # Get AI assistance info
        ai_info = self.detect_ai_assistance(pr_number)

        # Get reviews (single API call, reused below)
        reviews = self.get_pr_reviews(pr_number)

        # Get comments (pass reviews to avoid duplicate API call)
        comments_info = self.get_pr_comments(pr_number, reviews=reviews)

        # Calculate time metrics
        created_at = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        merged_at = datetime.strptime(pr["merged_at"], "%Y-%m-%dT%H:%M:%SZ")
        time_to_merge = (merged_at - created_at).total_seconds() / 3600  # hours

        # Time to first review
        time_to_first_review = None
        if reviews:
            first_review_time = min(
                datetime.strptime(r["submitted_at"], "%Y-%m-%dT%H:%M:%SZ")
                for r in reviews
                if r.get("submitted_at")
            )
            time_to_first_review = (first_review_time - created_at).total_seconds() / 3600

        # Count review iterations (CHANGES_REQUESTED reviews)
        changes_requested = sum(1 for r in reviews if r.get("state") == "CHANGES_REQUESTED")
        approvals = sum(1 for r in reviews if r.get("state") == "APPROVED")

        # Get unique reviewers (all and human-only)
        reviewers = set(r["user"]["login"] for r in reviews if r.get("user"))
        human_reviewers = set(
            r["user"]["login"]
            for r in reviews
            if r.get("user") and not self.is_bot_user(r["user"]["login"])
        )

        # Count substantive review submission comments (exclude approval-only and @coderabbit mentions)
        substantive_review_bodies = 0
        substantive_human_review_bodies = 0
        for review in reviews:
            body = review.get("body", "").strip()
            if body and review.get("id") not in comments_info.get("approval_review_ids", set()):
                substantive_review_bodies += 1
                # Exclude if user is bot or body mentions @coderabbit
                if review.get("user") and not self.is_bot_user(review["user"]["login"]):
                    if "@coderabbit" not in body.lower():
                        substantive_human_review_bodies += 1

        # Count all comments (inline + issue + substantive review bodies)
        total_all_comments = (
            len(comments_info["review_comments"])
            + len(comments_info["issue_comments"])
            + substantive_review_bodies
        )

        # Count comments excluding bots and @coderabbit mentions
        human_review_comments = [
            c
            for c in comments_info["review_comments"]
            if c.get("user")
            and not self.is_bot_user(c["user"]["login"])
            and "@coderabbit" not in c.get("body", "").lower()
        ]
        human_issue_comments = [
            c
            for c in comments_info["issue_comments"]
            if c.get("user")
            and not self.is_bot_user(c["user"]["login"])
            and "@coderabbit" not in c.get("body", "").lower()
        ]

        total_human_comments = (
            len(human_review_comments) + len(human_issue_comments) + substantive_human_review_bodies
        )

        return {
            "pr_number": pr_number,
            "title": pr["title"],
            "author": pr["user"]["login"],
            "created_at": pr["created_at"],
            "merged_at": pr["merged_at"],
            "url": pr["html_url"],
            # AI metrics
            "has_ai_assistance": ai_info["has_ai_assistance"],
            "ai_tools": ai_info["ai_tools"],
            "ai_commits_count": ai_info["ai_commits_count"],
            "total_commits": ai_info["total_commits"],
            "ai_percentage": ai_info["ai_percentage"],
            # Time metrics
            "time_to_merge_hours": time_to_merge,
            "time_to_merge_days": time_to_merge / 24,
            "time_to_first_review_hours": time_to_first_review,
            # Quality metrics (all users including bots)
            "changes_requested_count": changes_requested,
            "approvals_count": approvals,
            "reviewers_count": len(reviewers),
            "reviewers": list(reviewers),
            "review_comments_count": len(comments_info["review_comments"]),
            "issue_comments_count": len(comments_info["issue_comments"]),
            "total_comments_count": comments_info["total_comments"],
            # Quality metrics (excluding approval-only comments)
            "substantive_comments_count": total_all_comments,
            # Quality metrics (human-only, excluding bots like CodeRabbit and approval-only comments)
            "human_reviewers_count": len(human_reviewers),
            "human_reviewers": list(human_reviewers),
            "human_review_comments_count": len(human_review_comments),
            "human_issue_comments_count": len(human_issue_comments),
            "human_total_comments_count": len(human_review_comments) + len(human_issue_comments),
            "human_substantive_comments_count": total_human_comments,
            # Size metrics (from full PR details)
            "additions": pr_full.get("additions", 0),
            "deletions": pr_full.get("deletions", 0),
            "changed_files": pr_full.get("changed_files", 0),
        }
