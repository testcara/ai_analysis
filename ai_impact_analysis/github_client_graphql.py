"""
GitHub GraphQL API client for efficient PR data fetching with caching.

This client reduces API calls from ~500 to ~5-10 by using:
1. GraphQL API (fetch all PR data in 1-2 requests vs 5 per PR)
2. Caching layer (avoid re-fetching old PRs)
3. Incremental mode (only fetch new PRs since last run)
"""

import os
import json
import hashlib
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from ai_impact_analysis.logger import logger


class GitHubGraphQLClient:
    """Optimized GitHub client using GraphQL API with caching."""

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
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize GitHub GraphQL API client.

        Args:
            token: GitHub personal access token
            repo_owner: Repository owner/organization
            repo_name: Repository name
            cache_dir: Directory for caching PR data (default: .cache/github)
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo_owner = repo_owner or os.getenv("GITHUB_REPO_OWNER")
        self.repo_name = repo_name or os.getenv("GITHUB_REPO_NAME")

        if not self.token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable."
            )

        if not self.repo_owner or not self.repo_name:
            raise ValueError(
                "Repository owner and name are required. Set GITHUB_REPO_OWNER and GITHUB_REPO_NAME."
            )

        self.graphql_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Setup caching
        self.cache_dir = Path(cache_dir or ".cache/github")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_index_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_cache_index()

        logger.info(f"GitHub GraphQL client initialized for {self.repo_owner}/{self.repo_name}")
        logger.info(f"Cache directory: {self.cache_dir}")

    @staticmethod
    def is_bot_user(username: str) -> bool:
        """Check if a username belongs to a bot."""
        if not username:
            return False
        return username.lower() in GitHubGraphQLClient.BOT_USERS or username.lower().endswith(
            "[bot]"
        )

    def _load_cache_index(self) -> Dict[str, Any]:
        """Load cache index from disk."""
        if self.cache_index_file.exists():
            with open(self.cache_index_file, "r") as f:
                return json.load(f)
        return {"prs": {}, "last_fetch": {}}

    def _save_cache_index(self):
        """Save cache index to disk."""
        with open(self.cache_index_file, "w") as f:
            json.dump(self.cache_index, f, indent=2)

    def _get_cache_key(self, start_date: str, end_date: str, author: Optional[str] = None) -> str:
        """Generate cache key for a query."""
        key_parts = [self.repo_owner, self.repo_name, start_date, end_date, author or "all"]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()

    def _load_from_cache(self, cache_file: Path) -> Optional[List[Dict[str, Any]]]:
        """Load PR data from cache file."""
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data)} PRs from cache: {cache_file.name}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load cache file {cache_file}: {e}")
        return None

    def _save_to_cache(self, cache_file: Path, prs: List[Dict[str, Any]]):
        """Save PR data to cache file."""
        try:
            with open(cache_file, "w") as f:
                json.dump(prs, f, indent=2)
            logger.info(f"Saved {len(prs)} PRs to cache: {cache_file.name}")
        except Exception as e:
            logger.warning(f"Failed to save cache file {cache_file}: {e}")

    def fetch_merged_prs_graphql(
        self,
        start_date: str,
        end_date: str,
        author: Optional[str] = None,
        use_cache: bool = True,
        incremental: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch merged PRs using GraphQL API with caching.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            author: Optional author filter (GitHub username)
            use_cache: Use cached data if available
            incremental: Only fetch PRs updated since last run

        Returns:
            List of PR dictionaries with detailed metrics
        """
        cache_key = self._get_cache_key(start_date, end_date, author)
        cache_file = self.cache_dir / f"prs_{cache_key}.json"

        # Check cache
        if use_cache and not incremental:
            cached_data = self._load_from_cache(cache_file)
            if cached_data is not None:
                return cached_data

        # Determine date range for incremental mode
        query_start_date = start_date
        if incremental and cache_key in self.cache_index.get("last_fetch", {}):
            last_fetch = self.cache_index["last_fetch"][cache_key]
            logger.info(f"Incremental mode: fetching PRs updated since {last_fetch}")
            query_start_date = last_fetch

        # Fetch from GraphQL
        logger.info(f"Fetching PRs from GitHub GraphQL API ({query_start_date} to {end_date})")
        prs = self._fetch_prs_graphql_paginated(query_start_date, end_date, author)

        # Merge with cache in incremental mode
        if incremental and use_cache:
            cached_data = self._load_from_cache(cache_file)
            if cached_data:
                # Merge: update existing PRs, add new ones
                existing_pr_numbers = {pr["pr_number"] for pr in cached_data}
                new_prs = [pr for pr in prs if pr["pr_number"] not in existing_pr_numbers]
                prs = cached_data + new_prs
                logger.info(f"Merged {len(new_prs)} new PRs with {len(cached_data)} cached PRs")

        # Save to cache
        if use_cache:
            self._save_to_cache(cache_file, prs)
            self.cache_index["last_fetch"][cache_key] = datetime.now().strftime("%Y-%m-%d")
            self._save_cache_index()

        return prs

    def _fetch_prs_graphql_paginated(
        self, start_date: str, end_date: str, author: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch PRs using GraphQL with pagination.

        Args:
            start_date: Start date
            end_date: End date
            author: Optional author filter

        Returns:
            List of PR dictionaries
        """
        all_prs = []
        has_next_page = True
        cursor = None
        page = 1
        max_retries = 3

        while has_next_page:
            logger.info(f"Fetching GraphQL page {page}...")

            query = self._build_graphql_query(cursor)
            variables = {
                "owner": self.repo_owner,
                "name": self.repo_name,
                "states": ["MERGED"],
            }

            # Retry logic for timeouts
            for retry in range(max_retries):
                try:
                    response = requests.post(
                        self.graphql_url,
                        headers=self.headers,
                        json={"query": query, "variables": variables},
                        timeout=60,  # 60 second timeout
                    )
                    response.raise_for_status()
                    break  # Success, exit retry loop
                except requests.exceptions.Timeout:
                    if retry < max_retries - 1:
                        logger.warning(f"Request timeout, retrying ({retry + 1}/{max_retries})...")
                        time.sleep(2 ** retry)  # Exponential backoff: 1s, 2s, 4s
                    else:
                        logger.error("Max retries reached, request failed")
                        raise
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 504:  # Gateway timeout
                        if retry < max_retries - 1:
                            logger.warning(f"Server timeout (504), retrying ({retry + 1}/{max_retries})...")
                            time.sleep(2 ** retry)
                        else:
                            logger.error("Max retries reached after 504 errors")
                            raise
                    else:
                        raise

            data = response.json()

            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                break

            pr_data = data["data"]["repository"]["pullRequests"]
            prs_in_page = pr_data["nodes"]

            logger.info(f"Processing {len(prs_in_page)} PRs from page {page}...")

            # Track if we found any PRs in range on this page
            found_in_range = 0
            oldest_merged_in_page = None
            newest_merged_in_page = None
            filtered_reasons = {"not_merged": 0, "bot_author": 0, "author_mismatch": 0, "date_out_of_range": 0}

            # Process and filter PRs
            for pr_node in prs_in_page:
                pr_number = pr_node.get("number")

                # Track merged dates
                if pr_node.get("mergedAt"):
                    merged_at = datetime.strptime(pr_node["mergedAt"], "%Y-%m-%dT%H:%M:%SZ")
                    if oldest_merged_in_page is None or merged_at < oldest_merged_in_page:
                        oldest_merged_in_page = merged_at
                    if newest_merged_in_page is None or merged_at > newest_merged_in_page:
                        newest_merged_in_page = merged_at
                else:
                    filtered_reasons["not_merged"] += 1
                    continue

                # Check author (skip bots)
                pr_author = pr_node.get("author", {}).get("login", "") if pr_node.get("author") else ""
                if not pr_author or self.is_bot_user(pr_author):
                    filtered_reasons["bot_author"] += 1
                    continue

                # Filter by author if specified
                if author and pr_author != author:
                    filtered_reasons["author_mismatch"] += 1
                    continue

                # Filter by date range
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

                if not (start <= merged_at < end):
                    filtered_reasons["date_out_of_range"] += 1
                    continue

                # This PR matches all criteria
                pr_dict = self._process_pr_node(pr_node, start_date, end_date, author)
                if pr_dict:
                    all_prs.append(pr_dict)
                    found_in_range += 1

            # Log summary
            logger.info(f"Page {page} summary:")
            logger.info(f"  - Found {found_in_range}/{len(prs_in_page)} PRs in date range")
            if oldest_merged_in_page and newest_merged_in_page:
                logger.info(f"  - Merge dates on page: {oldest_merged_in_page.date()} to {newest_merged_in_page.date()}")
            logger.info(f"  - Filtered: {sum(filtered_reasons.values())} PRs")
            for reason, count in filtered_reasons.items():
                if count > 0:
                    logger.info(f"    • {reason}: {count}")
            logger.info(f"Total extracted: {len(all_prs)} relevant PRs so far...")

            # Check if we should continue searching
            # Since we order by UPDATED_AT but filter by MERGED_AT,
            # we need to search deeper to find older merged PRs
            should_continue = True

            # If we've checked 10 pages without finding anything, and
            # the oldest merged PR we've seen is still after our end_date, stop
            if page >= 10 and len(all_prs) == 0 and oldest_merged_in_page:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                if oldest_merged_in_page > end_dt:
                    logger.info(f"After {page} pages, oldest merged PR ({oldest_merged_in_page.date()}) is still after end date ({end_date})")
                    logger.info("PRs in your date range might be further back. Continuing search...")
                    # Don't stop, keep searching

            # Pagination
            has_next_page = pr_data["pageInfo"]["hasNextPage"]
            cursor = pr_data["pageInfo"]["endCursor"]
            page += 1

            # Small delay between pages to avoid rate limiting
            if has_next_page:
                time.sleep(0.5)  # 500ms delay between requests

            # Safety limit - increased to search deeper
            if page > 100:  # Max 100 pages = 2500 PRs
                logger.warning(f"Reached maximum page limit (100 pages). Found {len(all_prs)} PRs so far.")
                logger.warning("If this seems low, your target date range might be very old.")
                break

        logger.info(f"Fetched {len(all_prs)} PRs from GraphQL API")
        return all_prs

    def _build_graphql_query(self, after_cursor: Optional[str] = None) -> str:
        """Build GraphQL query for fetching PRs with all details in one request."""
        cursor_arg = f', after: "{after_cursor}"' if after_cursor else ""

        # Reduced limits to avoid 504 Gateway Timeout:
        # - 25 PRs per page (was 100)
        # - 30 commits per PR (was 100)
        # - 50 reviews per PR (was 100)
        # - 50 comments per PR (was 100)
        # Order by UPDATED_AT DESC to get recently active PRs first
        # (this helps find recent merges faster)
        return f"""
        query($owner: String!, $name: String!, $states: [PullRequestState!]) {{
          repository(owner: $owner, name: $name) {{
            pullRequests(
              first: 25{cursor_arg}
              states: $states
              orderBy: {{field: UPDATED_AT, direction: DESC}}
            ) {{
              pageInfo {{
                hasNextPage
                endCursor
              }}
              nodes {{
                number
                title
                url
                createdAt
                mergedAt
                updatedAt
                additions
                deletions
                changedFiles
                author {{
                  login
                }}
                commits(first: 30) {{
                  totalCount
                  nodes {{
                    commit {{
                      message
                    }}
                  }}
                }}
                reviews(first: 50) {{
                  totalCount
                  nodes {{
                    author {{
                      login
                    }}
                    state
                    submittedAt
                    body
                  }}
                }}
                reviewThreads(first: 50) {{
                  totalCount
                }}
                comments(first: 50) {{
                  totalCount
                  nodes {{
                    author {{
                      login
                    }}
                    body
                  }}
                }}
              }}
            }}
          }}
        }}
        """

    def _process_pr_node(
        self, pr_node: Dict[str, Any], start_date: str, end_date: str, author: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a PR node from GraphQL response into metrics dictionary.

        Args:
            pr_node: PR node from GraphQL
            start_date: Filter start date
            end_date: Filter end date
            author: Optional author filter

        Returns:
            PR metrics dictionary or None if filtered out
        """
        pr_number = pr_node.get("number")

        # Check if merged
        if not pr_node.get("mergedAt"):
            logger.debug(f"PR #{pr_number}: Not merged, skipping")
            return None

        # Check author (skip bots)
        pr_author = pr_node.get("author", {}).get("login", "") if pr_node.get("author") else ""
        if not pr_author or self.is_bot_user(pr_author):
            logger.debug(f"PR #{pr_number}: Bot author ({pr_author}), skipping")
            return None

        # Filter by author if specified
        if author and pr_author != author:
            logger.debug(f"PR #{pr_number}: Author mismatch ({pr_author} != {author}), skipping")
            return None

        # Filter by date range
        merged_at = datetime.strptime(pr_node["mergedAt"], "%Y-%m-%dT%H:%M:%SZ")
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        if not (start <= merged_at < end):
            logger.debug(f"PR #{pr_number}: Merged date {merged_at.date()} outside range ({start_date} to {end_date}), skipping")
            return None

        logger.debug(f"PR #{pr_number}: Matched! Author={pr_author}, Merged={merged_at.date()}")

        # Extract AI assistance info from commits
        ai_info = self._extract_ai_info(pr_node.get("commits", {}).get("nodes", []))

        # Calculate time metrics
        created_at = datetime.strptime(pr_node["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
        time_to_merge_hours = (merged_at - created_at).total_seconds() / 3600

        # Process reviews
        reviews = pr_node.get("reviews", {}).get("nodes", [])
        review_metrics = self._process_reviews(reviews, created_at)

        # Process comments
        comments = pr_node.get("comments", {}).get("nodes", [])
        comment_metrics = self._process_comments(comments, reviews)

        return {
            "pr_number": pr_node["number"],
            "title": pr_node["title"],
            "author": pr_author,
            "created_at": pr_node["createdAt"],
            "merged_at": pr_node["mergedAt"],
            "url": pr_node["url"],
            # AI metrics
            "has_ai_assistance": ai_info["has_ai_assistance"],
            "ai_tools": ai_info["ai_tools"],
            "ai_commits_count": ai_info["ai_commits_count"],
            "total_commits": pr_node.get("commits", {}).get("totalCount", 0),
            "ai_percentage": ai_info["ai_percentage"],
            # Time metrics
            "time_to_merge_hours": time_to_merge_hours,
            "time_to_merge_days": time_to_merge_hours / 24,
            "time_to_first_review_hours": review_metrics["time_to_first_review"],
            # Review metrics
            "changes_requested_count": review_metrics["changes_requested"],
            "approvals_count": review_metrics["approvals"],
            "reviewers_count": len(review_metrics["reviewers"]),
            "reviewers": list(review_metrics["reviewers"]),
            "human_reviewers_count": len(review_metrics["human_reviewers"]),
            "human_reviewers": list(review_metrics["human_reviewers"]),
            # Comment metrics
            "review_comments_count": pr_node.get("reviewThreads", {}).get("totalCount", 0),
            "issue_comments_count": pr_node.get("comments", {}).get("totalCount", 0),
            "total_comments_count": comment_metrics["total_comments"],
            "substantive_comments_count": comment_metrics["substantive_comments"],
            "human_total_comments_count": comment_metrics["human_comments"],
            "human_substantive_comments_count": comment_metrics["human_substantive"],
            "human_review_comments_count": 0,  # Not easily available in GraphQL
            "human_issue_comments_count": comment_metrics["human_issue_comments"],
            # Size metrics
            "additions": pr_node.get("additions", 0),
            "deletions": pr_node.get("deletions", 0),
            "changed_files": pr_node.get("changedFiles", 0),
        }

    def _extract_ai_info(self, commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract AI assistance information from commit messages."""
        ai_tools: Set[str] = set()
        ai_commits = 0
        total_commits = len(commits)

        for commit in commits:
            message = commit.get("commit", {}).get("message", "")

            # Check for AI assistance markers
            if "assisted-by: claude" in message.lower() or "co-authored-by: claude" in message.lower():
                ai_tools.add("Claude")
                ai_commits += 1

            if "assisted-by: cursor" in message.lower():
                ai_tools.add("Cursor")
                ai_commits += 1

        return {
            "has_ai_assistance": len(ai_tools) > 0,
            "ai_tools": sorted(list(ai_tools)),
            "ai_commits_count": ai_commits,
            "total_commits": total_commits,
            "ai_percentage": (ai_commits / total_commits * 100) if total_commits > 0 else 0,
        }

    def _process_reviews(
        self, reviews: List[Dict[str, Any]], created_at: datetime
    ) -> Dict[str, Any]:
        """Process review data to extract metrics."""
        reviewers: Set[str] = set()
        human_reviewers: Set[str] = set()
        changes_requested = 0
        approvals = 0
        time_to_first_review = None

        for review in reviews:
            author_login = review.get("author", {}).get("login") if review.get("author") else None

            if author_login:
                reviewers.add(author_login)
                if not self.is_bot_user(author_login):
                    human_reviewers.add(author_login)

            # Count review states
            state = review.get("state")
            if state == "CHANGES_REQUESTED":
                changes_requested += 1
            elif state == "APPROVED":
                approvals += 1

            # Calculate time to first review
            if review.get("submittedAt") and time_to_first_review is None:
                submitted_at = datetime.strptime(review["submittedAt"], "%Y-%m-%dT%H:%M:%SZ")
                time_to_first_review = (submitted_at - created_at).total_seconds() / 3600

        return {
            "reviewers": reviewers,
            "human_reviewers": human_reviewers,
            "changes_requested": changes_requested,
            "approvals": approvals,
            "time_to_first_review": time_to_first_review,
        }

    def _process_comments(
        self, comments: List[Dict[str, Any]], reviews: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process comment data to extract metrics."""
        total_comments = len(comments)
        human_comments = 0
        human_issue_comments = 0
        substantive_comments = 0
        human_substantive = 0

        # Process issue comments
        for comment in comments:
            author_login = comment.get("author", {}).get("login") if comment.get("author") else None
            body = comment.get("body", "").strip()

            if not body:
                continue

            substantive_comments += 1

            if author_login and not self.is_bot_user(author_login):
                if "@coderabbit" not in body.lower():
                    human_comments += 1
                    human_issue_comments += 1
                    human_substantive += 1

        # Process review bodies
        for review in reviews:
            body = review.get("body", "").strip()
            if not body:
                continue

            # Skip simple approval phrases
            if body.lower() in ["lgtm", "approved", "approve", "👍", ":+1:", "looks good"]:
                continue

            substantive_comments += 1

            author_login = review.get("author", {}).get("login") if review.get("author") else None
            if author_login and not self.is_bot_user(author_login):
                if "@coderabbit" not in body.lower():
                    human_comments += 1
                    human_substantive += 1

        return {
            "total_comments": total_comments,
            "substantive_comments": substantive_comments,
            "human_comments": human_comments,
            "human_substantive": human_substantive,
            "human_issue_comments": human_issue_comments,
        }

    def clear_cache(self, cache_key: Optional[str] = None):
        """
        Clear cache data.

        Args:
            cache_key: Optional specific cache key to clear. If None, clears all cache.
        """
        if cache_key:
            cache_file = self.cache_dir / f"prs_{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache: {cache_file.name}")
                if cache_key in self.cache_index.get("last_fetch", {}):
                    del self.cache_index["last_fetch"][cache_key]
                    self._save_cache_index()
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("prs_*.json"):
                cache_file.unlink()
            self.cache_index = {"prs": {}, "last_fetch": {}}
            self._save_cache_index()
            logger.info("Cleared all cache")
