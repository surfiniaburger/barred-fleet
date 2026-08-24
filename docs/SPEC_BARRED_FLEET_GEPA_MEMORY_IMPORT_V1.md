# Spec: BARRED-Fleet GEPA Memory Import V1

## Objective

Import local Graph-Powered GEPA evidence into the BARRED-Fleet cloud memory model without moving the live reflector, prompt mutation loop, or local Pareto ledger into Cloud Run.

The importer turns local GEPA artifacts into a small redacted memory document that can later be written to Firestore or attached to `/runs/{run_id}/report`.

Success means cloud BARRED-Fleet can say: “historical GEPA evidence exists for these taxonomy buckets and prompt variants,” while still preserving the rule that deterministic B-gate is the only vulnerability acceptance authority.

## Tech Stack

- Python 3.11
- BARRED-Fleet package under `barred-fleet/app`
- Existing local GEPA artifacts under `artifacts/gepa`
- Existing Step 4 audit receipt under `artifacts/metrics/step4_acceptance_report.json`
- Unit tests under `barred-fleet/tests/unit`

## Commands

Focused tests:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
uv run pytest tests/unit/test_gepa_memory.py -q
```

Adjacent memory tests:

```bash
uv run pytest tests/unit/test_gepa_memory.py tests/unit/test_reflection_memory.py -q
```

Full unit suite:

```bash
uv run pytest tests/unit -q
```

Local preview smoke:

```bash
make gepa-memory-preview-local
```

Authenticated remote preview smoke:

```bash
make gepa-memory-preview-smoke
```

Both:

```bash
make verify-gepa-memory-preview
```

Regenerate the local Step 4 audit receipt before importing headline metrics:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one
uv run python scripts/evaluate_step4_acceptance.py
```

## Project Structure

```text
barred-fleet/app/gepa_memory.py
  Pure GEPA artifact importer and redacted memory compiler.

barred-fleet/tests/unit/test_gepa_memory.py
  Contract tests with tiny local fixture artifacts.

GET /memory/gepa/preview
  Read-only API surface for redacted GEPA empirical memory preview.

docs/SPEC_BARRED_FLEET_GEPA_MEMORY_IMPORT_V1.md
  This migration specification.

artifacts/gepa/*
  Local GEPA research artifacts. These are read sources, not cloud runtime state.
```

## Configuration

Default local artifact source:

```text
BARRED_GEPA_MEMORY_SOURCE=local
BARRED_GEPA_PARETO_FRONTIER_PATH=../artifacts/gepa/pareto_frontier.json
BARRED_GEPA_MUTATIONS_PATH=../artifacts/gepa/mutations.jsonl
BARRED_GEPA_TRACES_PATH=../artifacts/gepa/traces.jsonl
BARRED_GEPA_ACCEPTANCE_REPORT_PATH=../artifacts/metrics/step4_acceptance_report.json
```

GCS redacted-summary source:

```text
BARRED_GEPA_MEMORY_SOURCE=gcs
BARRED_GEPA_MEMORY_GCS_URI=gs://<bucket>/memory/gepa/latest.json
```

The GCS path must point to an already-redacted `gepa_empirical_summary` JSON object or an envelope containing a `memory` object. It must not point to raw `traces.jsonl` or raw `pareto_frontier.json`.

## Code Style

Use pure functions with explicit path inputs and dictionary outputs:

```python
memory = compile_gepa_memory_from_artifacts(
    pareto_frontier_path=Path("artifacts/gepa/pareto_frontier.json"),
    mutations_path=Path("artifacts/gepa/mutations.jsonl"),
    traces_path=Path("artifacts/gepa/traces.jsonl"),
    acceptance_report_path=Path("artifacts/metrics/step4_acceptance_report.json"),
)
```

The importer must hash prompt bodies and never copy raw prompt, raw code, raw seed, or raw trace text into the output document.

## Testing Strategy

Unit tests use tiny JSON/JSONL files in a temporary directory.

Required behavior:

- compiles a stable `memory_id`
- emits `memory_kind=gepa_empirical_summary`
- summarizes Pareto frontier variants by taxonomy bucket
- summarizes mutation counts and topological rules without raw prompt bodies
- summarizes trace outcomes without raw predicate/code text
- includes Step 4 invariant receipt fields when available
- preserves redaction booleans as false
- rejects missing or malformed Pareto frontier input
- exposes a read-only preview endpoint that returns `attention_required` when artifacts are absent
- supports local artifact compilation and GCS redacted-summary preview modes

No test may call Gemini, Model Armor, Agent Gateway, GCS, or Firestore.

## Boundaries

- Always: treat GEPA import as evidence memory, not vulnerability acceptance.
- Always: keep B-gate as acceptance authority.
- Always: hash raw prompt text instead of storing it.
- Always: store large/raw artifacts in GCS later, not Firestore.
- Ask first: adding a Firestore writer for imported GEPA memory.
- Ask first: exposing GEPA memory through `/runs/{run_id}/report`.
- Ask first: enabling prompt mutation from imported Pareto variants.
- Never: store raw code, raw seeds, raw prompts, or trace predicate bodies in Firestore-ready memory.
- Never: mutate `artifacts/gepa` from Cloud Run local disk.
- Never: claim cloud self-evolution until opt-in prompt mutation is implemented and tested.

## Success Criteria

- `barred-fleet/app/gepa_memory.py` exposes a pure importer.
- `barred-fleet/tests/unit/test_gepa_memory.py` passes.
- Existing reflection memory tests still pass.
- The importer can read local GEPA artifacts but emits only redacted metadata.
- `/memory/gepa/preview` returns either `status=ok` with redacted memory or `status=attention_required` with a safe error.
- The output is suitable for future Firestore metadata storage.

## Open Questions

- Should imported GEPA memory be written to a separate collection (`barred_gepa_memory`) or merged into `barred_reflection_memory` with `memory_kind=gepa_empirical_summary`?
- Should cloud reports show only top Pareto variants, or also rejected/dead-end mutation summaries?
- Should future prompt selection use Pareto score alone or require a matching graph diagnostic bucket?
