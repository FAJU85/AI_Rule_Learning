# Blue-Green Deployment Strategy

This project is deployed as a Hugging Face Space. Blue-green releases use two
identical Spaces and an external router/load balancer that points production
traffic at exactly one color at a time.

## Environments

| Color | Purpose                              | Required setting    |
| ----- | ------------------------------------ | ------------------- |
| Blue  | Current or previous production Space | `BG_BLUE_SPACE_ID`  |
| Green | Idle release Space                   | `BG_GREEN_SPACE_ID` |

Both Spaces must use the same hardware tier, secrets, and environment variables.
Stateful services such as the Hugging Face dataset, caches, and any external
APIs remain shared so either color can serve production traffic after cutover.

## Configuration

Set these GitHub repository variables/secrets before enabling cutovers:

| Name                    | Type     | Description                                                       |
| ----------------------- | -------- | ----------------------------------------------------------------- |
| `BG_BLUE_SPACE_ID`      | variable | Blue Hugging Face Space id, for example `vooom/AI_Rule_Learning`. |
| `BG_GREEN_SPACE_ID`     | variable | Green Hugging Face Space id with matching configuration.          |
| `BG_HEALTH_PATH`        | variable | Health/smoke path, defaults to `/`.                               |
| `BG_ROUTER_CUTOVER_URL` | secret   | Router endpoint that switches traffic to the requested color.     |
| `BG_ROUTER_TOKEN`       | secret   | Optional bearer token for the router endpoint.                    |

The router endpoint receives this JSON payload:

```json
{
  "active_color": "green",
  "active_space_id": "vooom/AI_Rule_Learning_Green",
  "commit_sha": "<git sha>"
}
```

## Release flow

1. Confirm the current live color (`blue` or `green`).
2. Run the **Deploy to Hugging Face Space** workflow with operation
   `deploy-and-smoke` and the current live color.
3. The workflow deploys `space/` to the idle color and runs a smoke check against
   the idle Space URL.
4. Re-run the workflow with operation `deploy-and-cutover` after review. The
   `cutover` job uses the `production` environment as the manual approval gate.
5. Monitor errors, latency, logs, and the Space runtime for 5-10 minutes.
6. If the release is unhealthy, run operation `rollback` and set
   `rollback_color` to the previous known-good color.

## Database and state strategy

- Use additive, backward-compatible data changes only during a blue-green
  rollout. Add new fields before code requires them.
- Do not rename or delete fields until both colors have run successfully with the
  new shape and rollback is no longer required.
- Keep migrations reversible where possible and document manual repair steps for
  non-reversible data changes.
- Shared datasets and caches must tolerate both old and new application versions
  during the cutover window.

## Local commands

Preview the live/idle mapping:

```bash
BG_LIVE_COLOR=blue python scripts/blue_green.py plan
```

Smoke-test the idle environment:

```bash
BG_LIVE_COLOR=blue python scripts/blue_green.py smoke --color green
```

Cut traffic to green:

```bash
BG_ROUTER_CUTOVER_URL=https://router.example/cutover \
  python scripts/blue_green.py cutover --target-color green
```

Rollback to blue:

```bash
BG_ROUTER_CUTOVER_URL=https://router.example/cutover \
  python scripts/blue_green.py rollback --previous-color blue
```

## Rollback checklist

- Confirm the previous color is healthy.
- Run the workflow with operation `rollback` and the previous color.
- Verify the router points to the previous Space id.
- Monitor production error rate, latency, logs, and owner dashboard health for
  5-10 minutes.
- Keep the failed color available for investigation; do not overwrite it until
  the incident review is complete.
