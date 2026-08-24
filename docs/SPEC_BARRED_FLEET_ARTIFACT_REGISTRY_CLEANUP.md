# Spec: BARRED-Fleet Artifact Registry Cleanup

## Objective
Standardize artifact naming across curated and fresh BARRED runs without breaking existing path fields.
Users and demo surfaces should see canonical artifact roles (`corpus`, `attempts`, `deterministic_eval_result`, `diagnostic_receipt`) while older clients can continue using `input_path`, `attempts_path`, and related path keys.

## Tech Stack
- FastAPI report routes in `barred-fleet/app/fast_api_app.py`.
- Lifecycle/report aggregation in `barred-fleet/app/run_lifecycle.py`.
- Curated report assembly in `barred-fleet/app/demo.py` and `barred-fleet/app/tools.py`.
- Unit tests in `barred-fleet/tests/unit/`.

## Commands
- Focused lint: `cd barred-fleet && uv run ruff check app/run_lifecycle.py app/demo.py app/tools.py tests/unit/test_run_lifecycle.py tests/unit/test_demo.py tests/unit/test_tools.py`
- Focused tests: `cd barred-fleet && uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_demo.py tests/unit/test_tools.py -q`
- Unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Deployed demo verification after approval: `cd barred-fleet && make verify-demo`

## Project Structure
- `barred-fleet/app/run_lifecycle.py` exposes normalized artifact aliases for product run reports.
- `barred-fleet/app/tools.py` exposes normalized artifact aliases for ADK tool reports.
- `barred-fleet/app/demo.py` exposes normalized artifact aliases for `/demo/report` and uses them in the UI.
- `docs/` holds this specification.

## Code Style
Keep legacy path fields intact and add a canonical `artifact_registry` object.

```python
{
    "artifact_paths": {"input_path": "gs://.../training_corpus.jsonl"},
    "artifact_registry": {
        "corpus": {"path": "gs://.../training_corpus.jsonl", "available": True},
        "attempts": {"path": "gs://.../attempts.jsonl", "available": True},
        "deterministic_eval_result": {"path": "gs://.../deterministic_eval_result.json", "available": True},
        "diagnostic_receipt": {"path": "", "available": False},
    },
}
```

## Testing Strategy
- Unit-test normalized aliases for promoted fresh runs with GCS paths.
- Unit-test normalized aliases for blocked runs with diagnostic receipts.
- Unit-test curated demo/tool reports include the same alias object.
- No live model calls and no GCS writes for this slice.

## Boundaries
- Always: preserve existing `artifact_paths` keys for backward compatibility.
- Always: make canonical aliases additive and deterministic.
- Always: mark `diagnostic_receipt.available` true only when a receipt path exists.
- Ask first: deploy, mutate Firestore documents, or run live paid debate.
- Never: rename GCS objects in this slice.
- Never: infer artifact existence from a desired filename when no path is registered.

## Success Criteria
- Product reports include `artifact_registry` with canonical roles.
- Curated `/demo/report` includes `provenance.artifact_registry`.
- ADK `report_barred_run` tool payload includes `artifact_registry`.
- Blocked/failed product reports expose diagnostic receipt alias when present.
- Focused lint/tests and full unit suite pass.

## Open Questions
- Later slice can migrate actual GCS object names to a canonical directory schema; this slice only normalizes read/report contracts.
