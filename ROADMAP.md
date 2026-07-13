# Roadmap

This roadmap is directional and may change based on user feedback and maintainer capacity.

## Near Term

- Add explicit rule review states: pending, approved, rejected, active, stale, and needs_review.
- Add CLI commands for approving, rejecting, editing, merging, and scoring generated rules.
- Document a privacy-preserving, opt-in metrics plan to understand real adoption without collecting raw user content.
- Design a local management dashboard to replace confusing external analysis/management workflows.
- Improve README examples and screenshots.
- Extend dry-run coverage into any future dashboard actions; CLI and MCP write tools now support safe previews.
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
