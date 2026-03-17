"""AI-powered analysis of PR patterns."""

import json
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI


_MODEL = "gpt-4o-mini"
_MAX_PROMPT_CHARS = 60_000

_SYSTEM_PROMPT = """\
You are analyzing GitHub pull request data to extract the implicit, unwritten contribution rules of an open source project.
Your job is to identify patterns that are NEVER documented but are consistently enforced through reviews.
Focus on what differentiates merged PRs from rejected ones.
Be specific and concrete. No generic advice.
Respond ONLY with valid JSON matching the schema provided. No markdown, no preamble.\
"""

_JSON_SCHEMA = """{
  "summary": "2-3 sentence overview of this project's contribution culture",
  "pr_size_sweet_spot": {
    "insight": "string — what PR size gets merged fastest",
    "recommendation": "string — concrete advice"
  },
  "rejection_patterns": [
    {"pattern": "string", "example_quote": "string from an actual review", "how_to_avoid": "string"}
  ],
  "implicit_style_rules": [
    {"rule": "string", "evidence": "string — what review comments reveal this"}
  ],
  "maintainer_patterns": {
    "response_time": "string",
    "key_reviewers": "string",
    "other": "string"
  },
  "first_pr_checklist": ["string", "string", ...]
}"""


def _days_to_merge(pr: dict) -> int | None:
    """Return integer days between PR creation and merge, or None."""
    created = pr.get("created_at")
    merged = pr.get("merged_at")
    if not created or not merged:
        return None
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        delta = datetime.strptime(merged, fmt) - datetime.strptime(created, fmt)
        return max(0, delta.days)
    except ValueError:
        return None


def _compress_pr(pr: dict, status: str) -> str:
    """Compress a PR dict to a single compact string."""
    title = pr.get("title", "(no title)")
    files = pr.get("changed_files", 0)
    adds = pr.get("additions", 0)
    dels = pr.get("deletions", 0)
    size_str = f"files:{files} lines:+{adds}/-{dels}"

    if status == "MERGED":
        days = _days_to_merge(pr)
        days_str = f" | days_to_merge:{days}" if days is not None else ""
        header = f'[MERGED] "{title}" | {size_str}{days_str}'
    else:
        header = f'[REJECTED] "{title}" | {size_str}'

    reviews = pr.get("reviews", [])
    if reviews:
        review_lines = "\n".join(f'  Reviews: "{r[:200]}"' for r in reviews[:3])
        return f"{header}\n{review_lines}"
    return header


def _build_compressed_data(repo_data: dict) -> str:
    """Build the compressed PR data string, truncating if needed."""
    lines: list[str] = []

    for pr in repo_data["merged_prs"]:
        lines.append(_compress_pr(pr, "MERGED"))

    for pr in repo_data["rejected_prs"]:
        lines.append(_compress_pr(pr, "REJECTED"))

    full = "\n".join(lines)

    if len(full) > _MAX_PROMPT_CHARS:
        # Truncate from the middle (keep first merged, first rejected)
        full = full[:_MAX_PROMPT_CHARS] + "\n... [truncated]"

    return full


def analyze_repo_data(
    owner: str,
    repo: str,
    repo_data: dict[str, Any],
    github_token: str,
) -> dict[str, Any]:
    """Send PR data to AI and return parsed JSON analysis."""
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=github_token,
    )

    compressed = _build_compressed_data(repo_data)
    contributing = repo_data["metadata"].get("contributing_md") or "Not found"

    user_prompt = f"""\
Here is the PR history for {owner}/{repo}:

{compressed}

CONTRIBUTING.md content (if any):
{contributing[:3000] if len(contributing) > 3000 else contributing}

Extract contribution intelligence as JSON with exactly this schema:
{_JSON_SCHEMA}
"""

    def _call(extra_instruction: str = "") -> str:
        prompt = user_prompt
        if extra_instruction:
            prompt = extra_instruction + "\n\n" + user_prompt
        response = client.chat.completions.create(
            model=_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content

    raw = _call()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Retry once with explicit instruction
        raw = _call("Your previous response was not valid JSON. Respond with ONLY the JSON object.")
        return json.loads(raw)
