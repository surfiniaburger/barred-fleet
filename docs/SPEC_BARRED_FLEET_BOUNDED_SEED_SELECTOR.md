# Spec: BARRED-Fleet Bounded Seed Selector

## Objective

Allow fresh cloud debate runs to select a known seed from an allowlisted seed corpus without accepting arbitrary file paths or unbounded user input. The selector keeps `fixture:first` backward compatible and adds `cve500:N` for indexed access into the packaged 500-seed CVE corpus.

## Tech Stack

- Python/FastAPI service under `barred-fleet/app/`.
- ADK-compatible `/runs/fresh-demo` route.
- Packaged JSONL seed corpora under `barred-fleet/scenarios/debate/`.
- Deterministic unit tests under `barred-fleet/tests/unit/`.

## Commands

- Focused tests: `cd barred-fleet && uv run pytest tests/unit/test_fresh_debate.py -q`
- Full unit suite: `cd barred-fleet && uv run pytest tests/unit -q`
- Touched-file lint: `cd barred-fleet && uv run ruff check app/fresh_debate.py tests/unit/test_fresh_debate.py`
- Dry-run smoke: `cd barred-fleet && uv run python - <<'PY'`

## Project Structure

- `barred-fleet/app/fresh_debate.py` resolves seed IDs, creates run plans, and feeds selected seed content into the existing debate runtime.
- `barred-fleet/scenarios/debate/cve_seeds_test.jsonl` remains the backward-compatible fixture seed source.
- `barred-fleet/scenarios/debate/cve_seeds_500.jsonl` is the packaged allowlisted CVE seed source for `cve500:N`.
- `barred-fleet/tests/unit/test_fresh_debate.py` covers dry-run planning, rejection paths, and live-run payload handoff without paid model calls.

## Code Style

Seed selection stays behind a small interface:

```python
response = run_fresh_debate(
    FreshDebateRequest(seed_id="cve500:17", run_id="demo", dry_run=True)
)
```

The response includes metadata, not the full seed body:

```json
{
  "seed_id": "cve500:17",
  "source": "cve500",
  "source_file": "scenarios/debate/cve_seeds_500.jsonl",
  "index": 17,
  "language": "c",
  "predicate_sha256": "..."
}
```

## Testing Strategy

- Unit tests verify that `fixture:first` still plans successfully.
- Unit tests verify that `cve500:N` returns source, index, language, safety label, predicate hash, and topic hash.
- Unit tests reject malformed seed IDs such as `cve500:`, `cve500:-1`, and `cve500:abc`.
- Unit tests reject out-of-range indexes.
- Unit tests verify that live runner payloads receive the selected `topic` and `predicate`, using a fake runner only.

## Boundaries

- Always: Load `cve500:N` only from the packaged allowlisted `scenarios/debate/cve_seeds_500.jsonl` file.
- Always: Return provenance metadata in dry-run and live execution responses.
- Always: Keep `fixture:first` available for existing smoke tests and demo fixtures.
- Ask first: Add new seed families, GCS-backed seed selectors, or Firestore-backed seed selection.
- Ask first: Run paid live model calls.
- Never: Accept arbitrary user-supplied filesystem paths as seed IDs.
- Never: Return the full seed topic/code body in the planning response.

## Success Criteria

- `fixture:first` remains accepted.
- `cve500:0` and other valid indexes return a dry-run plan with bounded metadata.
- Malformed or unknown seed IDs fail closed with `attention_required`.
- Out-of-range indexes fail closed.
- The packaged seed file is included in the Cloud Run deployment context.
- Focused and full barred-fleet unit tests pass.

## Frontend Follow-Up

The minimal demo UI can safely expose this selector as a constrained dropdown or numeric field. It should call `/runs/fresh-demo` with `dry_run=true` first, render the returned metadata, and only enable live execution behind the existing server-side live flags. A later live debate window can stream or poll run events, but this selector slice does not require streaming changes.

## Open Questions

- Whether to add a curated `demo:N` seed family for cheaper, hand-picked demo examples.
- Whether promoted GCS seed storage should become a second allowlisted source after the hackathon submission freeze.
