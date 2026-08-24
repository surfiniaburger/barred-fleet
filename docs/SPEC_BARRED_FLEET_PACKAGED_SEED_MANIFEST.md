# Spec: BARRED-Fleet Packaged Seed Manifest

## Objective
Expose a read-only manifest for packaged seed sources so the demo can prove bounded seed selection without allowing arbitrary file paths or requiring GCS seed storage.
The manifest should make clear that `fixture:first` and `cve500:N` are allowlisted, packaged inputs, and that the 500-CVE file is available by index.

## Tech Stack
- Seed selector logic in `barred-fleet/app/fresh_debate.py`.
- FastAPI route in `barred-fleet/app/fast_api_app.py`.
- Demo UI in `barred-fleet/app/demo.py`.
- Unit tests in `barred-fleet/tests/unit/`.

## Commands
- Focused lint: `cd barred-fleet && uv run ruff check app/fresh_debate.py app/fast_api_app.py app/demo.py tests/unit/test_fresh_debate.py tests/unit/test_demo.py`
- Focused tests: `cd barred-fleet && uv run pytest tests/unit/test_fresh_debate.py tests/unit/test_demo.py -q`
- Unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Deployed verification after approval: `cd barred-fleet && make verify-demo`

## Project Structure
- `barred-fleet/app/fresh_debate.py` owns seed IDs and manifest generation.
- `barred-fleet/app/fast_api_app.py` exposes `GET /seeds/manifest`.
- `barred-fleet/app/demo.py` renders manifest metadata.
- `docs/` holds the spec.

## Code Style
Keep the manifest compact and hash-based; do not expose raw seed code or predicates.

```python
{
    "status": "ok",
    "sources": {
        "fixture": {"selector": "fixture:first", "count": 1},
        "cve500": {"selector": "cve500:N", "count": 500, "sha256": "..."},
    },
}
```

## Testing Strategy
- Unit-test manifest shape and seed counts.
- Unit-test `cve500` file hash is present and stable for the current packaged file.
- Route-test `GET /seeds/manifest`.
- Demo HTML test confirms the manifest is fetched and rendered.
- No paid model calls and no GCS access.

## Boundaries
- Always: keep seed selection allowlisted.
- Always: keep `fixture:first` backward compatible.
- Always: return only metadata, hashes, counts, and selector format.
- Ask first: move seeds to GCS, expose full seed text, or mutate seed files.
- Never: accept arbitrary file paths or user-supplied URLs as seeds.

## Success Criteria
- `GET /seeds/manifest` returns packaged source metadata.
- Manifest reports `cve500` count as `500` when the packaged seed file is present.
- Manifest includes source-file SHA-256 for provenance.
- Demo page renders packaged seed availability.
- Focused lint/tests and full unit suite pass.

## Open Questions
- Later slice can add an optional GCS manifest source, but packaged seeds remain the reliable demo default.
