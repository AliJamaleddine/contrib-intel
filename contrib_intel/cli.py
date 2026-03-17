"""CLI entry point for contrib-intel."""

import os
import re
import sys
from datetime import date

import click
from dotenv import load_dotenv

from .github_fetcher import fetch_repo_data
from .analyzer import analyze_repo_data
from .reporter import generate_report


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract owner and repo from a GitHub URL or owner/repo string."""
    # Handle owner/repo shorthand
    if re.match(r'^[\w.-]+/[\w.-]+$', url):
        owner, repo = url.split('/', 1)
        return owner, repo

    # Handle full GitHub URLs
    match = re.search(r'github\.com[/:]+([\w.-]+)/([\w.-]+?)(?:\.git)?/?$', url)
    if match:
        return match.group(1), match.group(2)

    raise click.BadParameter(
        f"Could not parse '{url}' as a GitHub repo URL. "
        "Expected format: https://github.com/owner/repo or owner/repo"
    )


@click.group()
def main():
    """contrib-intel — extract implicit contribution rules from GitHub PR history."""
    pass


@main.command()
@click.argument("repo_url")
@click.option(
    "--output",
    default="contrib-intel-report.md",
    show_default=True,
    help="Output file path for the Markdown report.",
)
@click.option(
    "--token",
    default=None,
    help="GitHub personal access token (overrides GITHUB_TOKEN env var).",
)
def analyze(repo_url: str, output: str, token: str | None):
    """Analyze a GitHub repository and produce a contribution intelligence report.

    REPO_URL can be a full GitHub URL (https://github.com/owner/repo)
    or a short form (owner/repo).
    """
    load_dotenv()

    # Resolve GitHub token
    github_token = token or os.environ.get("GITHUB_TOKEN")
    if not github_token:
        click.echo(
            "Error: GitHub token is required. Set GITHUB_TOKEN env var or use --token.",
            err=True,
        )
        sys.exit(1)

    # Resolve Anthropic API key
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        click.echo(
            "Error: ANTHROPIC_API_KEY env var is required.",
            err=True,
        )
        sys.exit(1)

    # Parse repo URL
    try:
        owner, repo = parse_repo_url(repo_url)
    except click.BadParameter as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Analyzing {owner}/{repo}...")

    # Step 1: Fetch data from GitHub
    click.echo("  Fetching merged PRs...")
    click.echo("  Fetching rejected PRs...")
    click.echo("  Fetching repo metadata...")
    try:
        repo_data = fetch_repo_data(owner, repo, github_token)
    except Exception as e:
        click.echo(f"Error fetching GitHub data: {e}", err=True)
        sys.exit(1)

    n_merged = len(repo_data["merged_prs"])
    n_rejected = len(repo_data["rejected_prs"])
    click.echo(f"  Found {n_merged} merged PRs and {n_rejected} rejected PRs.")

    # Step 2: Analyze with Claude
    click.echo("Analyzing PR patterns with Claude...")
    try:
        analysis = analyze_repo_data(owner, repo, repo_data, anthropic_key)
    except Exception as e:
        click.echo(f"Error during Claude analysis: {e}", err=True)
        sys.exit(1)

    # Step 3: Generate report
    click.echo(f"Writing report to {output}...")
    try:
        report = generate_report(
            owner=owner,
            repo=repo,
            analysis=analysis,
            n_merged=n_merged,
            n_rejected=n_rejected,
            generated_date=date.today().isoformat(),
        )
        with open(output, "w", encoding="utf-8") as f:
            f.write(report)
    except Exception as e:
        click.echo(f"Error writing report: {e}", err=True)
        sys.exit(1)

    click.echo(f"Done! Report saved to {output}")
