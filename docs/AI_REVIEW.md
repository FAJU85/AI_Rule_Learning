# AI Review Setup

This repository is prepared for CodeRabbit-based pull request review.

## Selected Integration

Priority option selected: **CodeRabbit**.

Reasons:

- automatic pull request review,
- maintainability feedback,
- security-oriented comments,
- lightweight repository configuration.

## Required GitHub Secret

Configure this repository secret before expecting AI review to run successfully:

```text
OPENAI_API_KEY
```

The workflow also uses the built-in `GITHUB_TOKEN`.

## Workflow

The workflow file is:

```text
.github/workflows/ai-review.yml
```

It runs on pull request open, synchronize, reopen, and ready-for-review events.

## Expected Behavior

When configured correctly, CodeRabbit posts automated review feedback on pull requests. Treat AI
review as advisory; maintainer review remains required for correctness, security, and project
direction.

## Fallback

If CodeRabbit is unavailable or credentials are not configured, maintainers can continue using GitHub
review plus the CI checks in `.github/workflows/ci.yml`.
