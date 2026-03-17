"""GitHub API fetcher — raw requests only, no PyGithub."""

import base64
from typing import Any

import requests


_BASE = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(url: str, token: str, params: dict | None = None) -> requests.Response:
    resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
    resp.raise_for_status()
    remaining = int(resp.headers.get("X-RateLimit-Remaining", 9999))
    if remaining < 10:
        print(f"⚠️  Warning: GitHub rate limit nearly exhausted ({remaining} requests remaining)")
    return resp


def _fetch_reviews(owner: str, repo: str, pr_number: int, token: str) -> list[str]:
    """Return list of non-empty review body texts for a PR."""
    url = f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    try:
        resp = _get(url, token, params={"per_page": 50})
        return [r["body"] for r in resp.json() if r.get("body", "").strip()]
    except requests.HTTPError:
        return []


def _pr_to_dict(pr: dict, reviews: list[str]) -> dict[str, Any]:
    return {
        "number": pr["number"],
        "title": pr.get("title", ""),
        "body": (pr.get("body") or "")[:500],
        "labels": [lb["name"] for lb in pr.get("labels", [])],
        "changed_files": pr.get("changed_files", 0),
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "merged_at": pr.get("merged_at"),
        "created_at": pr.get("created_at"),
        "reviews": reviews,
    }


def fetch_repo_data(owner: str, repo: str, token: str) -> dict[str, Any]:
    """Fetch merged PRs, rejected PRs, and repo metadata."""

    # --- Repo metadata ---
    meta_resp = _get(f"{_BASE}/repos/{owner}/{repo}", token)
    meta = meta_resp.json()

    contributing = None
    try:
        c_resp = _get(f"{_BASE}/repos/{owner}/{repo}/contents/CONTRIBUTING.md", token)
        encoded = c_resp.json().get("content", "")
        contributing = base64.b64decode(encoded).decode("utf-8", errors="replace")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            pass  # Not found — that's fine
        else:
            raise

    metadata = {
        "description": meta.get("description"),
        "language": meta.get("language"),
        "open_issues_count": meta.get("open_issues_count"),
        "contributing_md": contributing,
    }

    # --- Helper: fetch a page of closed PRs ---
    def fetch_closed_prs(per_page: int = 100, page: int = 1) -> list[dict]:
        resp = _get(
            f"{_BASE}/repos/{owner}/{repo}/pulls",
            token,
            params={"state": "closed", "per_page": per_page, "page": page, "sort": "updated", "direction": "desc"},
        )
        return resp.json()

    # --- Merged PRs (last 100 closed, keep merged) ---
    raw_closed = fetch_closed_prs(per_page=100)
    merged_raw = [pr for pr in raw_closed if pr.get("merged_at")]

    if len(merged_raw) < 20:
        print(
            f"⚠️  Warning: only {len(merged_raw)} merged PRs found — analysis may be limited"
        )

    merged_prs: list[dict] = []
    for pr in merged_raw:
        reviews = _fetch_reviews(owner, repo, pr["number"], token)
        merged_prs.append(_pr_to_dict(pr, reviews))

    # --- Rejected PRs (closed but NOT merged, up to 50) ---
    rejected_raw = [pr for pr in raw_closed if not pr.get("merged_at")][:50]

    rejected_prs: list[dict] = []
    for pr in rejected_raw:
        reviews = _fetch_reviews(owner, repo, pr["number"], token)
        rejected_prs.append(_pr_to_dict(pr, reviews))

    return {
        "merged_prs": merged_prs,
        "rejected_prs": rejected_prs,
        "metadata": metadata,
    }
