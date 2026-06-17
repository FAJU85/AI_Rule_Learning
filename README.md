# AI Rule Learning

Universal development environment setup reference and tooling guide for production-ready projects.

## Overview

This repository provides a project-agnostic development environment template covering:

- **SDLC** — linting, formatting, type checking, git hooks, commit standards, semantic versioning, changelog generation
- **Testing** — unit, integration, end-to-end, coverage reporting
- **Security** — dependency scanning, secret scanning, static analysis, security headers
- **CI/CD** — automated build, test, release, and deployment pipelines
- **SRE** — structured logging, metrics, health checks, tracing, alerting

See [README-DEVELOPMENT-1.md](./README-DEVELOPMENT-1.md) for the full tooling reference across all supported ecosystems.

## Quick Start

```bash
npm install
npm run validate
```

## Scripts

| Script                  | Description                      |
| ----------------------- | -------------------------------- |
| `npm run lint`          | Lint all Markdown files          |
| `npm run lint:fix`      | Auto-fix Markdown lint issues    |
| `npm run format`        | Format all files with Prettier   |
| `npm run format:check`  | Check formatting without writing |
| `npm run validate`      | Run lint + format check          |
| `npm run release`       | Create a release (auto bump)     |
| `npm run release:patch` | Bump patch version               |
| `npm run release:minor` | Bump minor version               |
| `npm run release:major` | Bump major version               |

## Commit Convention

This repository follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <subject>

Types: feat | fix | docs | style | refactor | perf | test | build | ci | chore | revert
```

Examples:

```text
docs: add python tooling reference
feat: add observability section to dev guide
fix: correct eslint configuration example
```

## CI/CD

| Workflow | Trigger            | Description                             |
| -------- | ------------------ | --------------------------------------- |
| CI       | push / PR          | Lint, format check, commit message lint |
| Security | push / PR / weekly | Secret scanning, dependency audit       |
| Release  | manual dispatch    | Version bump, changelog, git tag        |

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).
