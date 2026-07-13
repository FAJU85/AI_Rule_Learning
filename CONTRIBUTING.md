# Contributing

Thank you for helping improve **AI Rule Learning MCP**. This guide explains how to set up the
project, make changes, run checks, and submit high-quality pull requests.

---

## Setup

### Requirements

- Python 3.11+
- Node.js 22+
- npm
- Git

### Local setup

```bash
git clone https://github.com/faju85/ai_rule_learning.git
cd ai_rule_learning
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
npm install
npm run prepare
```

For MCP package work, install the MCP package in editable mode:

```bash
python -m pip install -e mcp
```

---

## Development workflow

1. Open or find an issue that describes the change.
2. Create a branch from `main`.
3. Make a focused change.
4. Add or update tests when behavior changes.
5. Run the required checks locally.
6. Commit using Conventional Commits.
7. Open a pull request using the PR template.

---

## Branch naming conventions

Use one of these prefixes:

| Prefix      | Use for                                         |
| ----------- | ----------------------------------------------- |
| `feat/`     | New features                                    |
| `fix/`      | Bug fixes                                       |
| `docs/`     | Documentation only                              |
| `test/`     | Tests only                                      |
| `refactor/` | Internal restructuring without behavior changes |
| `ci/`       | CI and workflow changes                         |
| `chore/`    | Maintenance                                     |

Examples:

```text
feat/memory-dry-run
fix/scheduler-status
docs/readme-quickstart
ci/labeler-workflow
```

---

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(optional-scope): <short summary>
```

Allowed types:

- `feat`
- `fix`
- `docs`
- `style`
- `refactor`
- `perf`
- `test`
- `build`
- `ci`
- `chore`
- `revert`

Rules enforced by commitlint:

- Keep the header under 100 characters.
- Use a lowercase subject.
- Keep one logical change per commit when possible.

---

## Testing requirements

Run these checks before opening a pull request:

```bash
ruff format --check .
npm run format:check
ruff check .
mypy src
pytest
python -m pytest -c /dev/null mcp/tests -q
```

Additional requirements:

- Bug fixes should include a regression test.
- New pure logic should include unit tests.
- New or changed user flows should include integration or end-to-end coverage when practical.
- Do not skip, delete, or weaken failing tests to make CI pass.

---

## Code style expectations

- Python code is formatted and linted with Ruff.
- Markdown, JSON, and YAML are formatted with Prettier.
- Markdown is linted with markdownlint.
- Use descriptive names and keep functions focused.
- Do not commit secrets, tokens, `.env` files, or private credentials.
- Avoid broad exception handling unless it is at a process boundary and clearly justified.

---

## Pull request requirements

Every pull request should include:

- A clear summary.
- Motivation or issue link.
- Description of changed files or behavior.
- Tests/checks run.
- Screenshots for visible UI changes, if applicable.
- Notes about risks, migrations, or follow-up work.

Before requesting review, confirm:

- CI passes.
- The PR is focused and reviewable.
- Documentation is updated when behavior changes.
- New dependencies are justified.
- Security-sensitive changes are called out explicitly.

---

## Review process

Maintainers may request changes for correctness, maintainability, safety, tests, or documentation.
CODEOWNERS is configured so repository owners are requested automatically for review.

---

## Security reports

Please do not disclose vulnerabilities publicly. Follow `SECURITY.md` for private reporting steps.
