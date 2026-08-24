# Spec: BARRED-Fleet Async Job Hardening

## Objective
Make product run lifecycle state explicit and auditable for demo and future production use.
A user should be able to create a bounded run, poll it, and understand whether it is queued, running, completed, blocked, or failed without inspecting backend logs.

## Tech Stack
- FastAPI product run routes in `barred-fleet/app/fast_api_app.py`.
- Lifecycle state in `barred-fleet/app/run_lifecycle.py`.
- Demo polling UI in `barred-fleet/app/demo.py`.
- Unit tests in `barred-fleet/tests/unit/test_run_lifecycle.py` and `barred-fleet/tests/unit/test_demo.py`.

## Commands
- Focused lint: `cd barred-fleet && uv run ruff check app/run_lifecycle.py app/demo.py tests/unit/test_run_lifecycle.py tests/unit/test_demo.py`
- Focused tests: `cd barred-fleet && uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_demo.py -q`
- Unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Deployed demo verification: `cd barred-fleet && make verify-demo`

## Project Structure
- `barred-fleet/app/run_lifecycle.py` owns lifecycle transitions, timestamps, duration, and error category.
- `barred-fleet/app/demo.py` renders polling status and terminal results.
- `docs/` holds this spec.

## Code Style
Use additive dictionary fields to preserve existing clients.

```python
{
    "status": "completed",
    "created_at": "2026-08-20T00:00:00Z",
    "queued_at": "2026-08-20T00:00:00Z",
    "started_at": "2026-08-20T00:00:01Z",
    "completed_at": "2026-08-20T00:00:05Z",
    "duration_ms": 4000,
    "error_category": "",
}
```

## Testing Strategy
- Unit-test queued payloads include `queued_at` and no terminal timestamps.
- Unit-test queued workers write `running` before terminal status.
- Unit-test completed/blocked/failed payloads include terminal timestamps and duration.
- Unit-test UI HTML includes clear polling labels.
- No paid model calls for this slice.

## Boundaries
- Always: preserve `/runs`, `/runs/{run_id}`, `/runs/{run_id}/report`, and `/runs/fresh-demo` compatibility.
- Always: keep live execution gated by backend env flags.
- Always: keep fields additive; do not rename existing response keys.
- Ask first: deploy, enable live flags, or run paid model calls.
- Never: fake B-gate success or deterministic eval receipts.

## Success Criteria
- Async product runs expose `queued → running → completed|blocked|failed` transitions.
- Lifecycle documents include `created_at`, `updated_at`, phase timestamp fields, `duration_ms`, and `error_category` where applicable.
- UI polling shows human-readable lifecycle phase text.
- Focused lint/tests and full unit suite pass.

## Open Questions
- Later slice can add a separate `b_gate_evaluating` status if B-gate execution becomes asynchronous.
