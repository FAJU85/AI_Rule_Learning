# Branch Protection Readiness

Use these settings for the `main` branch in GitHub repository settings.

## Recommended Rules

Enable branch protection for `main`:

- Require a pull request before merging.
- Require at least 1 approving review.
- Require review from CODEOWNERS.
- Dismiss stale pull request approvals when new commits are pushed.
- Require status checks to pass before merging.
- Require branches to be up to date before merging.
- Require conversation resolution before merging.
- Block force pushes.
- Block deletions.
- Restrict direct pushes to maintainers only, or block direct pushes entirely.

## Required Status Checks

Configure these checks as required after they have run at least once:

- `CI / Python quality and tests`
- `CI / Markdown and metadata`
- `Labeler / Apply PR labels`
- `AI Review / CodeRabbit review` when CodeRabbit credentials are configured

## Merge Policy

Recommended merge strategy:

- Squash merge for most pull requests.
- Preserve Conventional Commit style in squash commit title.
- Require passing CI before merge.
- Require security-sensitive changes to receive maintainer review.
