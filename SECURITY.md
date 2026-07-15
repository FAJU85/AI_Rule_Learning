# Security Policy

## Supported Versions

Security updates are provided for the latest released version and the current `main` branch.

| Version        | Supported   |
| -------------- | ----------- |
| Latest release | Yes         |
| `main`         | Yes         |
| Older releases | Best effort |

## Reporting a Vulnerability

Please do not report security vulnerabilities in public issues.

Email the maintainer with:

- a clear description of the vulnerability,
- affected files or versions,
- reproduction steps,
- potential impact,
- suggested fix, if known.

Contact: `info@tococolors.com`

## Maintainer Response

The maintainer aims to acknowledge reports within 7 days and provide an initial assessment or
follow-up plan as soon as practical.

## Scope

Security reports may include:

- secret exposure,
- unsafe file writes,
- prompt-injection handling concerns,
- dependency vulnerabilities,
- CI or release workflow weaknesses,
- unsafe scheduler behavior.

## Network Behavior

The MCP package is local-first by default. Outbound HTTPS calls are limited to optional Hugging Face features:

- personal backup/sync when both `HF_TOKEN` and `ARL_DATASET` are configured,
- anonymised community contribution when contribution is explicitly enabled,
- community template/pattern downloads used to improve local rule detection.

Set `ARL_OFFLINE=true` to disable all package-initiated Hugging Face/community network calls. In offline mode, the tool
uses only local files under `~/.ai-rule-learning/` and `sync_sessions` reports that offline mode is active.
