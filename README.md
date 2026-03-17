# contrib-intel

`contrib-intel` analyzes a GitHub repository's pull request history with AI and produces a Markdown report revealing the **implicit, unwritten rules** of that project — the patterns that actually get PRs merged vs. rejected, even when they're never documented anywhere.

## Installation

```bash
git clone https://github.com/your-username/contrib-intel
cd contrib-intel
pip install -e .
```

## Usage

If you have the [GitHub CLI](https://cli.github.com/) installed and authenticated, no configuration is needed:

```bash
contrib-intel analyze https://github.com/vitejs/vite
```

The token is auto-detected from `gh auth token`. If `gh` is not available, set `GITHUB_TOKEN` in your environment or `.env` file:

```bash
export GITHUB_TOKEN=ghp_your_token_here
contrib-intel analyze https://github.com/vitejs/vite
```

With options:

```bash
contrib-intel analyze https://github.com/vitejs/vite \
  --output vite-contribution-guide.md \
  --token ghp_your_token_here
```

A GitHub token with default public repo read access is sufficient for public repos. See `.env.example` for details.

### Sample output

```markdown
# Contribution Intelligence Report

**Repository:** vitejs/vite
**Generated:** 2024-11-15
**Based on:** 87 merged PRs · 23 rejected PRs

---

## TL;DR

vite is a fast-moving project with a strong bias toward small, focused PRs.
Maintainers are responsive but expect contributors to run the full test suite
and align changes with the existing plugin architecture before submitting.

---

## PR Size Sweet Spot

PRs touching fewer than 10 files and under 200 lines merge within 2-3 days.
Larger refactors sit open for weeks or stall without maintainer buy-in.

**Recommendation:** Keep your first PR under 150 lines. If you need a bigger
change, open an issue first to get maintainer signal before writing code.

---

## ✅ Your First PR Checklist

- [ ] Run `pnpm run build` and confirm no errors
- [ ] Add or update tests for your change
- [ ] Open an issue before implementing non-trivial features
```

## How it works

- **Fetches** the last 100 closed PRs (merged and rejected) from the GitHub REST API, including review comments for each
- **Compresses** PR data into a compact text format and sends it to an AI model with a structured prompt asking for pattern extraction
- **Renders** the AI's JSON response into a clean, actionable Markdown report you can reference when preparing your contribution

## Limitations

- **Public repos only** — GitHub tokens for private repos are not supported
- **Needs 20+ merged PRs** — the analysis degrades significantly with fewer PRs; very new or low-activity projects will produce weak results
- **AI can miss nuance** — AI-extracted patterns are probabilistic; always read some actual PR threads yourself before contributing
- **GitHub-only** — GitLab, Bitbucket, and other hosts are not supported
- **Rate limits** — GitHub's unauthenticated rate limit (60 req/hr) is too low; a token is required. The tool fetches ~150 API calls per run.

## License

MIT
