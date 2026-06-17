# Development Environment Setup

This document describes the development environment setup including E2E testing tools, SDLC tools, and SRE/observability tools. Tool choices are listed by category — pick the ones that match your project's language and surface type.

---

## Installed Tools

### E2E Testing Tools

| Category            | Tool                   | Ecosystem                   | Purpose                                                               |
| ------------------- | ---------------------- | --------------------------- | --------------------------------------------------------------------- |
| **Web E2E**         | Playwright             | Node / Python / Java / .NET | Cross-browser automation; ideal for modern SPAs and headless CI       |
|                     | Cypress                | Node                        | In-browser frontend testing; fast feedback loop for JS-heavy apps     |
|                     | Selenium WebDriver     | Any (Java, Python, C#, JS)  | Mature, broad browser/language support                                |
|                     | Puppeteer              | Node                        | Headless Chrome automation; programmatic use                          |
| **Mobile E2E**      | Appium                 | Any                         | Cross-platform native, hybrid, and mobile-web testing (iOS + Android) |
|                     | Detox                  | Node (React Native)         | End-to-end testing for React Native apps                              |
| **API E2E**         | Newman / Postman       | Any                         | Collection-based API test execution in CI                             |
|                     | pytest + httpx         | Python                      | Async-friendly API and integration tests                              |
|                     | REST Assured           | Java                        | Fluent HTTP assertions for JVM projects                               |
| **Bot / Messaging** | Telethon / Pyrogram    | Python                      | MTProto userbot driver for Telegram bots                              |
|                     | Slack Bolt (test mode) | Node / Python               | Event-driven testing for Slack apps                                   |

### SDLC Tools (Code Quality & Collaboration)

| Category             | Tool                                   | Ecosystem      | Purpose                                       |
| -------------------- | -------------------------------------- | -------------- | --------------------------------------------- |
| **Linting**          | ESLint                                 | Node / JS / TS | JavaScript / TypeScript static analysis       |
|                      | Ruff / Flake8                          | Python         | Fast Python linting                           |
|                      | Checkstyle / SpotBugs                  | Java           | Style enforcement and bug detection           |
|                      | golangci-lint                          | Go             | Comprehensive Go linter suite                 |
| **Formatting**       | Prettier                               | Node / JS / TS | Opinionated code formatter                    |
|                      | Black / isort                          | Python         | Deterministic Python formatting               |
|                      | gofmt                                  | Go             | Standard Go formatter                         |
| **Type Checking**    | TypeScript (`tsc`)                     | Node           | Static type checking                          |
|                      | mypy / pyright                         | Python         | Python type annotation enforcement            |
| **Git Hooks**        | Husky + lint-staged                    | Node           | Pre-commit / commit-msg hooks for JS projects |
|                      | pre-commit                             | Any            | Multi-language hook framework                 |
| **Commit Standards** | Commitlint + Commitizen                | Node           | Enforce and assist Conventional Commits       |
|                      | commitizen (Python)                    | Python         | Same convention, Python toolchain             |
| **Versioning**       | Standard Version / Release-it          | Node           | Changelog generation and semver releases      |
|                      | bump2version / python-semantic-release | Python         | Equivalent for Python projects                |

### SRE Tools (Observability & Reliability)

| Category               | Tool                              | Ecosystem | Purpose                                                  |
| ---------------------- | --------------------------------- | --------- | -------------------------------------------------------- |
| **Structured Logging** | Winston                           | Node      | JSON-structured application logging                      |
|                        | Loguru / structlog                | Python    | Structured logging with context binding                  |
|                        | Logback / Log4j 2                 | Java      | Configurable JVM logging                                 |
|                        | zap                               | Go        | High-performance structured logging                      |
| **Metrics**            | Prometheus client (`prom-client`) | Node      | Expose `/metrics` in Prometheus format                   |
|                        | `prometheus-client`               | Python    | Same for Python services                                 |
|                        | Micrometer                        | Java      | Metrics facade for JVM (Prometheus, Datadog, etc.)       |
| **Health Checks**      | Custom middleware                 | Any       | Liveness and readiness endpoints (see §Health Endpoints) |
| **HTTP Logging**       | Morgan                            | Node      | HTTP request logging middleware                          |
|                        | Uvicorn / Gunicorn access logs    | Python    | ASGI / WSGI request logging                              |
| **Security Headers**   | Helmet                            | Node      | Sets secure HTTP response headers                        |
|                        | `secure` / `django-csp`           | Python    | Equivalent header enforcement                            |
| **Rate Limiting**      | express-rate-limit                | Node      | Request throttling middleware                            |
|                        | slowapi / Flask-Limiter           | Python    | Rate limiting for ASGI/WSGI apps                         |

### Unit & Integration Test Frameworks

| Tool                 | Ecosystem      | Purpose                                       |
| -------------------- | -------------- | --------------------------------------------- |
| **Vitest**           | Node / TS      | Fast Vite-native unit testing with coverage   |
| **Jest**             | Node / JS / TS | General-purpose JS/TS testing with mocking    |
| **pytest**           | Python         | Feature-rich Python test runner with fixtures |
| **JUnit 5**          | Java / Kotlin  | Standard JVM test framework                   |
| **RSpec**            | Ruby           | BDD-style testing                             |
| **Go test**          | Go             | Built-in Go test runner                       |
| **@testing-library** | Node           | DOM and component assertion utilities         |
| **jsdom**            | Node           | Lightweight DOM environment for unit tests    |

---

## Common Commands

Commands follow the pattern `<package-manager> run <script>` for Node projects, or the equivalent for your ecosystem. Adapt the table below to your toolchain.

### Development & Build

| Action               | Node (npm/pnpm/yarn) | Python (uv/pip)             | Java (Maven)           | Go                  |
| -------------------- | -------------------- | --------------------------- | ---------------------- | ------------------- |
| Start dev server     | `npm run dev`        | `uvicorn main:app --reload` | `mvn spring-boot:run`  | `go run .`          |
| Build for production | `npm run build`      | `python -m build`           | `mvn package`          | `go build ./...`    |
| Type check           | `npm run typecheck`  | `mypy .`                    | `mvn compile`          | `go vet ./...`      |
| Generate types/code  | `npm run types`      | `datamodel-codegen …`       | `mvn generate-sources` | `go generate ./...` |
| Deploy               | `npm run deploy`     | _project-specific_          | `mvn deploy`           | _project-specific_  |

### Code Quality

| Action       | Node                   | Python               | Java                   | Go                        |
| ------------ | ---------------------- | -------------------- | ---------------------- | ------------------------- |
| Lint         | `npm run lint`         | `ruff check .`       | `mvn checkstyle:check` | `golangci-lint run`       |
| Lint + fix   | `npm run lint:fix`     | `ruff check . --fix` | —                      | `golangci-lint run --fix` |
| Format       | `npm run format`       | `black . && isort .` | —                      | `gofmt -w .`              |
| Format check | `npm run format:check` | `black --check .`    | —                      | `gofmt -l .`              |

### Testing

| Action           | Node                      | Python                  | Java                     | Go                     |
| ---------------- | ------------------------- | ----------------------- | ------------------------ | ---------------------- |
| Run unit tests   | `npm run test`            | `pytest tests/unit`     | `mvn test`               | `go test ./...`        |
| Watch mode       | `npm run test:watch`      | `pytest-watch`          | —                        | `gotestsum --watch`    |
| With coverage    | `npm run test:coverage`   | `pytest --cov`          | `mvn test jacoco:report` | `go test -cover ./...` |
| Test UI          | `npm run test:ui`         | —                       | —                        | —                      |
| E2E (Playwright) | `npm run test:e2e`        | `pytest e2e/`           | —                        | —                      |
| E2E headed       | `npm run test:e2e:headed` | `pytest e2e/ --headed`  | —                        | —                      |
| E2E debug        | `npm run test:e2e:debug`  | `PWDEBUG=1 pytest e2e/` | —                        | —                      |
| E2E (Cypress)    | `npm run cy:run`          | —                       | —                        | —                      |
| Cypress UI       | `npm run cy:open`         | —                       | —                        | —                      |

### Git Hooks & Releases

| Action             | Node                    | Python / Any         |
| ------------------ | ----------------------- | -------------------- |
| Interactive commit | `npm run commit`        | `cz commit`          |
| New release        | `npm run release`       | `semantic-release`   |
| Patch release      | `npm run release:patch` | `bump2version patch` |
| Minor release      | `npm run release:minor` | `bump2version minor` |
| Major release      | `npm run release:major` | `bump2version major` |

---

## Health Endpoints

Any service should expose these standard health and observability endpoints. The paths below are conventional; adapt to your framework's routing.

| Endpoint        | Method | Description                                       | Example response                                 |
| --------------- | ------ | ------------------------------------------------- | ------------------------------------------------ |
| `/health`       | `GET`  | Full health check including dependency status     | `{ status, timestamp, uptime, version, checks }` |
| `/health/live`  | `GET`  | Liveness probe — is the process alive?            | `{ status: "alive", timestamp, uptime }`         |
| `/health/ready` | `GET`  | Readiness probe — can the service handle traffic? | `{ ready, status, checks }`                      |
| `/metrics`      | `GET`  | Prometheus metrics in exposition format           | Prometheus text format                           |

**Implementation pointers by ecosystem:**

- **Node (Express):** `express-actuator` or custom middleware in `src/middleware/health.ts`
- **Python (FastAPI):** `/health` route returning Pydantic model; `prometheus-fastapi-instrumentator` for `/metrics`
- **Python (Django):** `django-health-check` + `django-prometheus`
- **Java (Spring Boot):** Spring Actuator (`/actuator/health`, `/actuator/prometheus`) out of the box
- **Go:** `net/http` handler or `go-chi` route; `prometheus/client_golang` for metrics

---

## Getting Started

These steps apply regardless of language or framework. Replace `<package-manager>` and commands with the equivalents from the **Common Commands** table above.

1. **Install dependencies**

   ```bash
   # Node
   npm install

   # Python
   pip install -r requirements.txt   # or: uv sync

   # Java
   mvn install

   # Go
   go mod download
   ```

2. **Set up environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your local configuration — never commit this file
   ```

3. **Initialize git hooks**

   ```bash
   # Node (Husky)
   npm run prepare

   # Any language (pre-commit)
   pre-commit install
   ```

4. **Verify the setup — run the full quality gate locally before your first commit**

   ```bash
   # Lint
   <package-manager> run lint

   # Type check
   <package-manager> run typecheck    # or equivalent

   # Unit tests
   <package-manager> run test

   # E2E tests (optional at setup; run against a local or staging server)
   <package-manager> run test:e2e
   ```

5. **Start the development server**

   ```bash
   <package-manager> run dev    # or equivalent
   ```

---

## License

MIT
