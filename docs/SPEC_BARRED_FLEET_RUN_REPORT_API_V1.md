# Spec: BARRED-Fleet Product Run Report API v1

## Objective
Add a stable read-only report endpoint for product-shaped BARRED runs.
The endpoint lets the demo UI, `agents-cli`, or a future dashboard ask for a
single run summary without knowing whether the run is still planned, blocked,
failed, or completed.
When accepted corpus artifacts exist, the endpoint enriches the lifecycle
metadata with deterministic artifact facts.

## Tech Stack
- FastAPI route in `barred-fleet/app/fast_api_app.py`.
- Lifecycle aggregation in `barred-fleet/app/run_lifecycle.py`.
- Existing `FreshDebateRequest` and run status registry remain unchanged.
- No live model call, GCS write, Firestore write, or B-gate execution is
  triggered by the report endpoint.
- Artifact-backed enrichment reuses existing offline BARRED report builders.

## Commands
- Focused tests: `cd barred-fleet && uv run pytest tests/unit/test_run_lifecycle.py -q`
- Unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Focused lint: `cd barred-fleet && uv run ruff check app/run_lifecycle.py app/fast_api_app.py tests/unit/test_run_lifecycle.py`

## Project Structure
- `barred-fleet/app/run_lifecycle.py` owns product run status and report
  aggregation.
- `barred-fleet/app/fast_api_app.py` exposes the REST endpoint.
- `barred-fleet/tests/unit/test_run_lifecycle.py` covers lifecycle/report
  contracts.
- `docs/` holds the implementation spec.

## Code Style
Use plain dictionaries consistent with the existing BARRED-Fleet route style.
The report is additive over existing status payloads and does not mutate state.

```python
{
    "status": "ok",
    "run_id": run_id,
    "lifecycle": lifecycle_payload,
    "b_gate": {"available": True, "passed": True},
}
```

## Testing Strategy
- Unit-test the pure report builder with injected status readers.
- Route-test `GET /runs/{run_id}/report` against the in-memory registry.
- Unit-test artifact enrichment with local fixture paths before remote GCS
  usage.
- Preserve existing `/runs`, `/runs/{run_id}`, `/runs/fresh-demo`, and
  `/demo/report` behavior.

## Boundaries
- Always: return a deterministic report from persisted lifecycle metadata.
- Always: preserve blocked/failed diagnostic receipts as first-class evidence.
- Always: treat artifact enrichment as additive; if artifact reads fail, return
  lifecycle facts plus an enrichment error rather than failing the endpoint.
- Ask first: trigger live fresh debate, mutate Cloud Run flags, or deploy.
- Never: report a blocked run as B-gate evaluated when no B-gate artifact exists.
- Never: expose raw seed topic/predicate text in diagnostic receipts.

## Success Criteria
- `GET /runs/{run_id}/report` returns `status=ok` for known planned, blocked,
  failed, or completed product runs.
- Unknown runs return `status=not_found`.
- Blocked/failed runs include diagnostic receipt metadata and mark B-gate as
  unavailable.
- Completed runs include promotion/artifact paths and B-gate availability.
- Completed runs with readable artifacts include accepted/rejected counts,
  verifier rates, B-gate metrics, and deterministic eval summary.
- Focused and unit tests pass without paid model calls.

## Open Questions
- A later slice can update the demo UI to render the enriched product report
  fields instead of only showing lifecycle status.
