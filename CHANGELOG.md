# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
[Conventional Commits](https://www.conventionalcommits.org/), with versions
managed by [standard-version](https://github.com/conventional-changelog/standard-version).

## [Unreleased]

### Added

- Universal development environment setup reference (`README-DEVELOPMENT-1.md`)
- `package.json` with scripts for linting, formatting, and versioning
- Markdown linting via `markdownlint-cli2` (`.markdownlint.json`)
- Code formatting via `Prettier` (`.prettierrc.json`)
- Git hooks via `Husky` — pre-commit and commit-msg hooks
- Pre-commit validation via `lint-staged`
- Conventional commit enforcement via `commitlint` (`.commitlintrc.json`)
- Semantic versioning via `standard-version` (`.versionrc.json`)
- GitHub Actions CI workflow (lint, format check, commit message lint)
- GitHub Actions Security workflow (secret scanning, dependency audit)
- GitHub Actions Release workflow (manual dispatch, version bump, changelog)
- `README.md` with project overview and usage
- `CONTRIBUTING.md` with development workflow guidelines
- `CHANGELOG.md` (this file)
- `.editorconfig` for editor consistency
- `.gitignore`
