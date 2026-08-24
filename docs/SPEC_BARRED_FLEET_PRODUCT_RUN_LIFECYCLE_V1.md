# Spec: BARRED-Fleet Product Run Lifecycle v1

## Assumptions

1. This is post-submission roadmap work against the active working copy, not the frozen submitted artifact.
2. The existing `/runs/fresh-demo` endpoint, bounded seed selector, live flags, packaged debate runtime, fresh artifact reporter, GCS uploader, and Firestore registry writer are working foundations and must not be rebuilt.
3. The first product-shaped API can be synchronous internally as long as it exposes a durable status document through `GET /runs/{run_id}`.
4. Full background queues, Pub/Sub, Cloud Tasks, Model Armor, Agent Gateway, and reflection/Pareto prompt evolution are out of scope for this slice.
5. Firestore remains metadata-only. Large corpus, attempts, checkpoint, record, cassette, and deterministic receipt artifacts stay in GCS or local runtime files.
6. The default deployment posture remains closed: live fresh debate and promotion are disabled unless explicit environment flags are enabled.

If any assumption is wrong, revise this spec before implementation.

## Objective

Wrap the existing demo-scoped fresh debate path in a product-shaped run API:

```text
POST /runs
  → validate bounded seed request
  → create/update durable run status metadata
  → delegate to existing fresh debate planner/executor
  → promote passing artifacts through existing GCS + Firestore writer
  → record completion/failure status

GET /runs/{run_id}
  → return durable run status metadata
```

The user is a judge, operator, or future UI client that wants to start a bounded fresh vulnerability debate and see durable cloud-backed run state without relying on a one-off demo endpoint.

Success means BARRED-Fleet can truthfully claim a product run lifecycle, not only a curated report path:

```text
seed_id → POST /runs → status document → fresh artifacts → deterministic B-gate
        → optional GCS promotion → Firestore run status → GET /runs/{run_id}
```

## Relationship To Existing Specs

This spec extends, rather than replaces:

- `docs/SPEC_BARRED_FLEET_FRESH_CLOUD_DEBATE.md`
- `docs/SPEC_BARRED_FLEET_BOUNDED_SEED_SELECTOR.md`
- `docs/SPEC_BARRED_FLEET_RUN_REGISTRY_AND_ARTIFACTS.md`
- `docs/BARRED_FLEET_ROADMAP_EXECUTION_PLAN.md`

Existing `/runs/fresh-demo` remains backward compatible for the current UI and smoke tests.

## Tech Stack

- Python `>=3.11`
- FastAPI in `barred-fleet/app/fast_api_app.py`
- Pydantic request models in `barred-fleet/app/fresh_debate.py` or a new small `barred-fleet/app/run_lifecycle.py`
- Existing fresh debate planner/executor in `barred-fleet/app/fresh_debate.py`
- Existing fresh artifact promotion in `barred-fleet/app/fresh_artifacts.py`
- Existing Firestore dependency from `google-cloud-firestore`
- Existing GCS dependency through `gcsfs`
- Unit tests under `barred-fleet/tests/unit/`

## Commands

Baseline before implementation:

```bash
cd barred-fleet
uv run pytest tests/unit/test_fresh_debate.py tests/unit/test_fresh_artifacts.py tests/unit/test_demo.py -q
make verify-demo
```

Focused tests after implementation:

```bash
cd barred-fleet
uv run pytest tests/unit/test_run_lifecycle.py tests/unit/test_fresh_debate.py tests/unit/test_fresh_artifacts.py -q
```

Full unit suite after implementation:

```bash
cd barred-fleet
uv run pytest tests/unit -q
```

Lint touched files:

```bash
cd barred-fleet
uv run ruff check app/fast_api_app.py app/fresh_debate.py app/fresh_artifacts.py app/run_lifecycle.py tests/unit/test_run_lifecycle.py
```

Cloud verification stays opt-in:

```bash
cd barred-fleet
make verify-demo
```

Do not add paid live model calls to `make verify-demo`.

## Project Structure

Expected files:

```text
barred-fleet/app/fast_api_app.py             Adds POST /runs and GET /runs/{run_id}
barred-fleet/app/run_lifecycle.py            Product run status API, request mapping, Firestore status writer/reader
barred-fleet/app/fresh_debate.py             Existing planner/executor; only touch if a small seam is required
barred-fleet/app/fresh_artifacts.py          Existing promotion; only touch if status payload needs a returned field
barred-fleet/app/demo.py                     Optional UI follow-up; not required for first API slice
barred-fleet/tests/unit/test_run_lifecycle.py New product API/status tests with fake writers/readers
docs/SPEC_BARRED_FLEET_PRODUCT_RUN_LIFECYCLE_V1.md This spec
```

## API Contract

### `POST /runs`

Request:

```json
{
  "seed_id": "fixture:first",
  "run_id": "fresh-product-demo-001",
  "dry_run": false,
  "max_attempts": 1,
  "timeout_seconds": 180,
  "model_routes": {
    "generator": "vertex_ai/gemini-3.5-flash-lite",
    "judge": "vertex_ai/gemini-3.6-flash",
    "verifier": "vertex_ai/gemini-3.6-flash"
  }
}
```

Rules:

- `seed_id` accepts only existing allowlisted seed IDs: `fixture:first` or `cve500:N`.
- `max_attempts` defaults to `1`.
- Product live execution still requires the same live flags as `/runs/fresh-demo`.
- `dry_run=true` creates a `planned` status and must not call model routes.
- `dry_run=false` creates `running`, then updates to `completed` or `failed`.

Synchronous response, first slice:

```json
{
  "status": "completed",
  "run_id": "fresh-product-demo-001",
  "seed_id": "fixture:first",
  "run_status_uri": "/runs/fresh-product-demo-001",
  "b_gate_passed": true,
  "promotion": {
    "status": "promoted",
    "reason": "gcs_and_firestore_written"
  },
  "artifact_paths": {
    "input_path": "gs://.../training_corpus.jsonl",
    "attempts_path": "gs://.../attempts.jsonl",
    "deterministic_eval_result_path": "gs://.../deterministic_eval_result.json"
  }
}
```

If live execution is disabled, return `attention_required` as current code does, and write a status document with `status="blocked"` if a valid run ID exists.

### `GET /runs/{run_id}`

Response:

```json
{
  "run_id": "fresh-product-demo-001",
  "status": "completed",
  "seed_id": "fixture:first",
  "seed_metadata": {
    "source": "fixture",
    "source_file": "scenarios/debate/cve_seeds_test.jsonl",
    "index": 0,
    "language": "c",
    "original_safety": "vulnerable",
    "predicate_sha256": "...",
    "topic_sha256": "..."
  },
  "model_routes": {
    "generator": "vertex_ai/gemini-3.5-flash-lite",
    "judge": "vertex_ai/gemini-3.6-flash",
    "verifier": "vertex_ai/gemini-3.6-flash"
  },
  "max_attempts": 1,
  "created_at": "2026-08-20T00:00:00Z",
  "updated_at": "2026-08-20T00:00:10Z",
  "b_gate_passed": true,
  "promotion_status": "promoted",
  "artifact_paths": {
    "input_path": "gs://...",
    "attempts_path": "gs://...",
    "deterministic_eval_result_path": "gs://..."
  },
  "error": null
}
```

Unknown run IDs return:

```json
{
  "status": "not_found",
  "run_id": "missing-run"
}
```

## Firestore Status Document

Use the existing Firestore database/project configuration:

```text
BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION=barred_runs
BARRED_RUN_REGISTRY_FIRESTORE_PROJECT=gem-creation
BARRED_RUN_REGISTRY_FIRESTORE_DATABASE=barred-fleet
```

Document ID:

```text
<run_id>
```

Fields written at start:

```json
{
  "run_id": "<run_id>",
  "status": "running",
  "seed_id": "cve500:1",
  "seed_metadata": {},
  "model_routes": {},
  "max_attempts": 1,
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC"
}
```

Fields updated on completion/failure:

```json
{
  "status": "completed",
  "updated_at": "ISO-8601 UTC",
  "b_gate_passed": true,
  "promotion_status": "promoted",
  "promotion_reason": "gcs_and_firestore_written",
  "artifact_paths": {},
  "error": null
}
```

Firestore status metadata may duplicate artifact registry fields, but it must not store large JSONL content.

## Code Style

Keep lifecycle code as a thin orchestration layer over existing functions:

```python
async def create_product_run(request: FreshDebateRequest) -> dict[str, Any]:
    initial = build_running_status(plan)
    write_status(plan.run_id, initial)
    result = await run_fresh_debate_async(request)
    final = build_final_status(plan=plan, result=result)
    write_status(plan.run_id, final)
    return summarize_product_run_response(final)
```

Conventions:

- Prefer pure builders for status payloads.
- Inject Firestore reader/writer in tests; do not require live cloud services for unit tests.
- Preserve existing `attention_required` response semantics.
- Avoid broad exception swallowing except at route boundaries, where failures become structured `failed` status documents.

## Testing Strategy

Unit tests:

- `POST /runs` with `dry_run=true` writes/plans a `planned` status and does not call live runner.
- `POST /runs` with live disabled returns `attention_required` and records `blocked`.
- `POST /runs` with fake successful runner records `completed`, B-gate status, promotion status, and artifact paths.
- `POST /runs` with fake failing runner records `failed` with error text.
- `GET /runs/{run_id}` returns injected status payload.
- `GET /runs/{run_id}` returns `not_found` for missing run.
- `/runs/fresh-demo` behavior remains unchanged.

No unit test may call live Gemini/Vertex/Ollama models, real Firestore, or real GCS.

Optional manual cloud test after approval:

```bash
curl -sS -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -X POST \
  "https://barred-fleet-837262597425.us-east1.run.app/runs" \
  -d '{"seed_id":"fixture:first","run_id":"fresh-product-smoke","dry_run":true,"max_attempts":1}'
```

## Boundaries

- Always:
  - Keep `make verify-demo` deterministic and non-paid.
  - Keep `/runs/fresh-demo` backward compatible.
  - Keep live execution disabled by default.
  - Keep `max_attempts=1` for demo/product smoke paths unless explicitly overridden and allowed by policy.
  - Write Firestore metadata only; store artifacts in GCS.
  - Preserve deterministic B-gate as the acceptance authority.

- Ask first:
  - Enabling live fresh debate in Cloud Run.
  - Enabling artifact promotion in Cloud Run.
  - Running paid Gemini/Vertex model calls.
  - Adding a queue service, new cloud service, or new dependency.
  - Changing Cloud Run authentication or IAM.

- Never:
  - Store raw code bodies, full corpus JSONL, or attempts JSONL directly in Firestore.
  - Let Gemini narration decide acceptance.
  - Break the curated `pilot-v1-calibrated-pecan` report path.
  - Remove existing `/runs/fresh-demo` or demo UI behavior.
  - Claim Model Armor, Agent Gateway, Agent Runtime, or async queue support from this slice.

## Success Criteria

- `POST /runs` exists and delegates to the existing fresh debate path.
- `GET /runs/{run_id}` exists and returns durable status metadata.
- Start status records include `status`, `seed_metadata`, `model_routes`, `max_attempts`, and `created_at`.
- Completion/failure records include `status`, `b_gate_passed`, `promotion.status`, `artifact_paths`, and `error`.
- `/runs/fresh-demo` remains available and tests continue to pass.
- Focused and full unit tests pass.
- No paid model calls are required for unit tests or `make verify-demo`.

## Open Questions

1. Should `POST /runs` default to `dry_run=true` for safety, or require the caller to pass `dry_run=false` explicitly for live execution?
2. Should `GET /runs/{run_id}` read from the same `barred_runs` Firestore document used by artifact registry lookup, or should status live in a separate collection such as `barred_run_status`?
3. Should failed fresh runs be promoted to GCS for auditability, or should only B-gate-passing runs be promoted in this slice?
4. Should the existing `/demo` UI switch to `POST /runs`, or should that wait until the API is deployed and manually verified?
