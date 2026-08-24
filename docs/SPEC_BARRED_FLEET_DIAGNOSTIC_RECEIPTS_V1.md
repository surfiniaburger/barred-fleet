# Spec: BARRED-Fleet Diagnostic Receipts v1

## Objective

Make blocked and failed product runs auditable without requiring a paid live model call or a passing B-gate artifact set.

Today, passing fresh runs can produce and promote deterministic B-gate receipts. Blocked and failed runs mainly exist as lifecycle status documents. This slice adds a small deterministic diagnostic receipt for blocked/failed runs so every run can leave an audit artifact:

```text
blocked|failed lifecycle status
  -> diagnostic_receipt.json
  -> lifecycle status includes diagnostic_receipt_path
  -> optional GCS upload when promotion is enabled and configured
```

## Tech Stack

- Python `>=3.11`
- Existing `barred-fleet/app/run_lifecycle.py`
- Existing GCS uploader and Firestore env configuration from `barred-fleet/app/fresh_artifacts.py`
- Unit tests under `barred-fleet/tests/unit/`

## Commands

```bash
cd barred-fleet
uv run ruff check app/run_lifecycle.py tests/unit/test_run_lifecycle.py
uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_fresh_artifacts.py -q
uv run pytest tests/unit -q
```

## Project Structure

```text
barred-fleet/app/run_lifecycle.py              Writes diagnostic receipts for blocked/failed final states
barred-fleet/tests/unit/test_run_lifecycle.py  Covers receipt creation and optional promotion
docs/SPEC_BARRED_FLEET_DIAGNOSTIC_RECEIPTS_V1.md This spec
```

## Code Style

Keep receipt generation pure and deterministic:

```python
receipt_path = write_diagnostic_receipt(plan=plan, status_payload=final_status)
final_status["diagnostic_receipt_path"] = receipt_path
```

The receipt is small JSON metadata only. It must not include raw source code, full corpus JSONL, attempts JSONL, or model outputs.

## Testing Strategy

- Unit tests use a temporary run directory.
- Unit tests inject uploader/writer fakes where needed.
- No test calls live GCS, Firestore, Gemini, Vertex, or Ollama.
- Existing passing-run promotion tests must remain unchanged.

## Boundaries

- Always:
  - Write diagnostic receipts only for `blocked` and `failed`.
  - Keep passing-run B-gate receipt behavior unchanged.
  - Include `run_id`, `status`, `seed_metadata`, `model_routes`, `max_attempts`, `error`, `required_env`, and timestamps.
  - Store only receipt paths in Firestore lifecycle status.

- Ask first:
  - Uploading blocked/failed full artifacts.
  - Adding a separate bucket or Firestore collection.
  - Running paid live model calls.

- Never:
  - Put raw code, full JSONL artifacts, or large model transcripts in Firestore.
  - Treat a diagnostic receipt as a passing deterministic eval.
  - Change `/runs/fresh-demo` behavior.

## Success Criteria

- Blocked runs write a local `diagnostic_receipt.json`.
- Failed runs write a local `diagnostic_receipt.json`.
- Lifecycle final status includes `diagnostic_receipt_path`.
- If promotion is enabled and GCS bucket is configured, diagnostic receipt uploads to GCS and lifecycle status stores the GCS path.
- Full unit suite passes.

## Open Questions

1. Should future failed runs also upload checkpoint/record/cassette artifacts when present?
2. Should diagnostic receipts get a separate `diagnostic_receipt_contract` eval metric later?
