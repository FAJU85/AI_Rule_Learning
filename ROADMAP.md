# Roadmap

This roadmap is directional and may change based on user feedback and maintainer capacity.

## Near Term

- Expand owner-dashboard controls with richer operational audit history and screenshots.
- Continue improving stale/needs_review rule-health automation and duplicate-rule suggestions in the private owner dashboard.
- Extend the privacy-preserving, opt-in metrics baseline with owner-dashboard charts and optional aggregate upload.
- Improve the private owner-only Hugging Face Space dashboard/control panel for operations, rule review, and project health.
- Improve README examples and screenshots.
- Extend dry-run coverage into future owner-dashboard actions; CLI and MCP write tools now support safe previews.
- Expand test coverage for CLI and MCP workflows.
- Improve generated-rule review and rollback guidance.

## Mid Term

- Add richer example projects and session fixtures.
- Improve contributor onboarding and issue triage automation.
- Add clearer compatibility documentation for supported AI clients.
- Improve observability around sync and scheduler behavior.

## Long Term

- Provide a stronger manual approval flow for generated rules.
- Explore richer policy validation and safety checks.
- Improve multi-agent workflow support.
- Publish stable release guidance for package consumers.

## Infrastructure reliability

- Blue-green production releases: maintain blue and green Hugging Face Spaces, deploy to the idle color, run smoke
  tests, use manual approval for cutover, and keep one-command rollback documented in
  `docs/BLUE_GREEN_DEPLOYMENT.md`.
