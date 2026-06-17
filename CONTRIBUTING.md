# Contributing

## Getting Started

```bash
git clone https://github.com/faju85/ai_rule_learning.git
cd ai_rule_learning
npm install
```

## Development Workflow

1. Create a branch: `git checkout -b feat/your-feature`
2. Make your changes
3. Run validation: `npm run validate`
4. Commit using Conventional Commits format
5. Push and open a pull request against `main`

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<optional-scope>): <description>

[optional body]

[optional footer]
```

**Allowed types:**

| Type       | Use for                             |
| ---------- | ----------------------------------- |
| `feat`     | New content or feature              |
| `fix`      | Corrections or bug fixes            |
| `docs`     | Documentation changes               |
| `style`    | Formatting only (no content change) |
| `refactor` | Restructuring without new content   |
| `perf`     | Performance improvements            |
| `test`     | Adding or updating tests            |
| `build`    | Build system changes                |
| `ci`       | CI/CD configuration changes         |
| `chore`    | Maintenance tasks                   |
| `revert`   | Reverting a previous commit         |

Additional constraints enforced by commitlint:

- **Header** must not exceed **100 characters**
- **Subject** must use lowercase only

Commit messages are linted automatically on commit via Husky + commitlint.

## Code Quality

All Markdown files are linted with `markdownlint` and formatted with `Prettier`. Run:

```bash
npm run lint:fix   # auto-fix markdownlint issues
npm run format     # auto-format with Prettier
```

Pre-commit hooks run automatically when you commit via `git commit`.

## Pull Request Guidelines

- Keep PRs focused on a single concern
- Update the relevant documentation sections
- Ensure CI passes before requesting review
- Use a descriptive PR title following the commit convention

## Release Process

Releases are managed via `standard-version` and triggered manually through the GitHub Actions Release workflow.
Maintainers are responsible for releases.
