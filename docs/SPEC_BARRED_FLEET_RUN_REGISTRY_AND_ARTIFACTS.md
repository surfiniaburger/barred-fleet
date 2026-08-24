# Spec: BARRED-Fleet Run Registry And Artifact Resolution

## Objective

Build the next small bridge from curated demo to promised cloud workflow: a run registry that maps `run_id` values to reportable BARRED artifacts.

The user is a security/platform reviewer who should not need to know internal JSONL paths. Success means `report_barred_run(run_id=...)` and `/demo/report?run_id=...` can resolve a registered run from metadata, compute the deterministic B-gate report, and preserve the existing fixture fallback.

This slice is intentionally local-file backed. Firestore and GCS are the next backend implementations after the interface is stable.

## Tech Stack

- Python `>=3.11`
- FastAPI
- Google ADK / `agents-cli`
- Existing BARRED deterministic tools in `barred-fleet/app/tools.py`
- Local JSON registry file for this slice

## Commands

Run unit tests:

```bash
cd barred-fleet && uv run pytest tests/unit -q
```

Dry-check demo smoke command:

```bash
cd barred-fleet && make -n demo-smoke
```

Authenticated cloud smoke:

```bash
cd barred-fleet && make demo-smoke
```

## Project Structure

```text
barred-fleet/app/run_registry.py                 Local run registry resolver
barred-fleet/app/tools.py                        Uses registry before fixture fallback
barred-fleet/app/demo.py                         Supports report rendering by run_id
barred-fleet/app/fast_api_app.py                 Exposes /demo/report?run_id=...
barred-fleet/barred_runtime/run_registry.json    Packaged demo registry
barred-fleet/tests/unit/                         Registry and report tests
```

## Code Style

Use small pure functions with explicit path-safety boundaries:

```python
def resolve_run_artifacts(run_id: str, *, registry_path: Path) -> dict[str, str | float]:
    registry = load_run_registry(registry_path)
    return registry.get(run_id, {})
```

Conventions:

- Registry values are metadata, not loaded artifacts.
- Large JSONL artifacts stay outside the registry.
- Explicit tool arguments override registry defaults.
- Registry fallback must not break the existing curated fixture behavior.

## Testing Strategy

Unit tests cover:

- Missing registry file returns an empty mapping.
- Malformed registry payload raises a clear `ValueError`.
- Registered run IDs resolve to artifact paths.
- Explicit tool arguments override registry values.
- Unknown run IDs still return `attention_required`.
- `/demo/report?run_id=...` returns the selected run report.

No test should require Firestore, GCS, Cloud Run, or live model calls.

## Boundaries

- Always:
  - Preserve local BARRED behavior.
  - Keep deterministic B-gate as the source of acceptance truth.
  - Keep fixture fallback for `pilot-v1-calibrated-pecan`.
  - Keep tests runnable offline.

- Ask first:
  - Adding Firestore or GCS dependencies.
  - Changing Cloud Run authentication.
  - Triggering fresh paid model/debate runs.
  - Making graph/prefilter mandatory.

- Never:
  - Store large JSONL artifact content in Firestore-like metadata.
  - Let registry metadata override explicit user/tool arguments.
  - Treat cassette replay as provider-side cache telemetry.
  - Claim full fresh debate execution in Cloud Run from this slice.

## Success Criteria

- `report_barred_run(run_id=...)` resolves registry entries before fixture fallback.
- `/demo/report` keeps the current default demo.
- `/demo/report?run_id=pilot-v1-calibrated-pecan` returns the same passing report.
- Unknown run IDs return `attention_required` with a clear error.
- `cd barred-fleet && uv run pytest tests/unit -q` passes.

## Open Questions

- Should the next backend implementation be GCS-first, Firestore-first, or both together?
- Should registry writes happen from local batch completion, cloud upload, or an explicit import command?
