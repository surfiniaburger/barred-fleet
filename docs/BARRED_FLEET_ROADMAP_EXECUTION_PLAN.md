# BARRED-Fleet Roadmap Execution Plan

## Objective

Move BARRED-Fleet from a curated run-reporting demo to a production-shaped cloud debate system without breaking the existing local BARRED flow.

The immediate submitted system is intentionally narrow:

```text
run ID → Firestore metadata → private GCS artifacts → deterministic B-gate → ADK narration
```

The roadmap extends that into:

```text
seed input → cloud debate execution → artifact upload → Firestore run record → deterministic B-gate → report/UI/eval
```

## Non-Negotiable Constraints

- Preserve local BARRED compatibility.
- Keep `report_barred_run(run_id=...)` stable.
- Keep deterministic acceptance separate from model narration.
- Keep Cloud Run private unless explicitly recording demo proof.
- Do not store large code/corpus bodies in Firestore; store metadata and URIs.
- Do not claim roadmap services are implemented until verified.
- Use small slices that each have tests and a deploy/verifier command.

## Current Baseline

```text
Cloud Run service: barred-fleet
Project: gem-creation
Region: us-east1
Latest validated revision: barred-fleet-00038-skl
Runtime identity: barred-fleet-runtime@gem-creation.iam.gserviceaccount.com
Demo run: pilot-v1-calibrated-pecan
B-gate: PASS
accepted rows: 5 / 5
verifier parse OK: 1.0
verifier pass: 0.75
deterministic eval score: 1.0
```

Baseline verification:

```bash
cd barred-fleet
make verify-demo
```

Do not start roadmap work unless the baseline passes or the failure is understood and documented.

## Phase 0 — Submission Freeze

### Goal

Freeze the submitted artifact so eligibility is not weakened by post-deadline edits.

### Tasks

1. Confirm Devpost fields are pasted from `docs/DEVPOST_FINAL_FIELDS.md`.
2. Upload final public demo video.
3. Include architecture diagram or screenshot.
4. Link the repo.
5. Confirm disclosures mention pre-existing BARRED harness and new BARRED-Fleet adapter.
6. Run `make verify-demo`.
7. Stop editing submitted materials after the deadline.

### Done Criteria

- Devpost submission accepted.
- Video URL is public and playable.
- Repo link works in incognito or is shared with required hackathon emails.
- `make verify-demo` passes.
- `barred-fleet/demo/README.md` indexes final evidence.

## Phase 1 — Extract BARRED-Fleet Into A Clean Repo

### Goal

Create a product-shaped repo for BARRED-Fleet while preserving a pointer back to the Silver-One research checkout.

### Recommended Repo Shape

```text
barred-fleet/
  app/
  barred_runtime/
  deployment/
  demo/
  docs/
  scripts/
  tests/
  Makefile
  README.md
  pyproject.toml
  uv.lock
```

### Tasks

1. Create a new repo or fork after submission freeze.
2. Copy `barred-fleet/` as the root project.
3. Copy only docs needed for BARRED-Fleet:
   - `docs/DEVPOST_FINAL_FIELDS.md`
   - `docs/BARRED_FLEET_AGENT_HANDOFF.md`
   - `docs/BARRED_FLEET_ROADMAP_EXECUTION_PLAN.md`
   - `docs/SUBMISSION_FREEZE_CHECKLIST.md`
   - `docs/SPEC_BARRED_FLEET_CLOUD_ARTIFACT_REGISTRY.md`
4. Decide whether `barred_runtime/` should vendor only the deterministic code needed for B-gate/reporting or depend on Silver-One as a package.
5. Ensure `make test-unit` and `make verify-demo` still work from the new repo root.

### Test Gate

```bash
make test-unit
make verify-demo
```

### Risk

The main risk is accidentally copying unrelated research artifacts or relying on parent-relative paths. Fix by making BARRED-Fleet paths root-relative and adding tests for packaged artifact resolution.

## Phase 2 — GCS Artifact Upload Lifecycle

### Goal

Add a controlled write path that uploads run artifacts to GCS after a local or cloud debate run.

### Proposed Contract

```bash
python scripts/upload_run_artifacts.py \
  --run-id <run_id> \
  --corpus <path/to/corpus.jsonl> \
  --attempts <path/to/attempts.jsonl> \
  --deterministic-eval <path/to/result.json> \
  --bucket gs://gem-creation-barred-fleet-artifacts
```

### Tasks

1. Define a manifest schema:
   - `run_id`
   - `artifact_kind`
   - `gcs_uri`
   - `sha256`
   - `byte_size`
   - `created_at`
   - `producer`
2. Upload artifacts to:
   - `runs/<run_id>/training_corpus.jsonl`
   - `runs/<run_id>/artifacts/attempts/<run_id>.jsonl`
   - `runs/<run_id>/eval/deterministic_eval_result.json`
3. Verify hash after upload by reading the GCS object back.
4. Emit a local manifest JSON.
5. Do not expose write endpoints publicly.

### Test Gate

- Unit-test manifest construction.
- Unit-test path validation.
- Use fake GCS writer in unit tests.
- Add one explicit live command for manual upload verification.

### Acceptance

- Uploaded artifacts can be resolved by `report_barred_run`.
- No Firestore write is needed yet; use GCS registry JSON or local manifest for the first slice.

## Phase 3 — Firestore Run Write Lifecycle

### Goal

Write run metadata to Firestore after artifact upload.

### Firestore Document Shape

```json
{
  "run_id": "run-id",
  "status": "ready",
  "input_path": "gs://bucket/runs/run-id/training_corpus.jsonl",
  "attempts_path": "gs://bucket/runs/run-id/artifacts/attempts/run-id.jsonl",
  "deterministic_eval_result_path": "gs://bucket/runs/run-id/eval/deterministic_eval_result.json",
  "b_gate_passed": true,
  "accepted_rows": 5,
  "attempt_rows": 17,
  "min_verifier_parse_ok_rate": 1.0,
  "created_at": "ISO-8601",
  "cloud_run_revision": "revision-if-known",
  "artifact_bucket": "gs://bucket"
}
```

### Tasks

1. Add `scripts/write_run_metadata.py`.
2. Validate required fields before writing.
3. Keep Firestore document small: metadata only.
4. Add idempotent upsert behavior.
5. Add dry-run mode.
6. Add read-after-write verification.

### Test Gate

- Unit-test payload validation.
- Unit-test idempotent document path construction.
- Unit-test read-after-write using fake Firestore reader/writer.

### Cloud IAM

Do not broaden the existing runtime read role. For writes, create a separate ingestion identity with scoped write permissions. Runtime service should remain read-only unless there is a clear reason to allow writes.

## Phase 4 — Fresh Cloud Debate Execution

### Current Status

Current safe UI revision is `barred-fleet-00038-skl`:

- `POST /runs/fresh-demo` exists.
- Dry-run planning supports `fixture:first` and packaged `cve500:N` seeds.
- The `/demo` UI previews seed source, index, language, safety label, and predicate hash before live execution.
- Non-dry-run execution refuses safely while `BARRED_ENABLE_LIVE_FRESH_DEBATE=false`.
- Live execution also requires `BARRED_START_INTERNAL_DEBATE_STACK=true`.
- Live execution is capped at one attempt by default with `BARRED_MAX_LIVE_FRESH_ATTEMPTS=1`.
- The deployed revision includes the packaged runtime files, but `BARRED_START_INTERNAL_DEBATE_STACK=false` in Cloud Run.
- Bounded live execution is wired behind explicit environment flags and has been exercised; selected seeds may pass or fail B-gate.
- Packaged stack lifecycle code is test-covered in `barred-fleet/app/debate_stack.py`.
- Minimal debate runtime files are packaged under `barred-fleet/src/agentbeats/` and `barred-fleet/scenarios/debate/`.
- `make verify-packaged-stack` starts and cleans up the packaged localhost A2A stack without model inference.

### Live Attempt Evidence

Bounded live attempts were made and then live execution was disabled again:

- `fresh-live-20260818-204505` failed before model execution because the Cloud Run app could not import packaged `agentbeats`; fixed by adding `BARRED_DEBATE_RUNTIME_ROOT` to the import path.
- `fresh-live-20260818-205036` exposed an A2A client compatibility bug: the copied client sent a raw `Message`, but the installed A2A SDK requires `SendMessageRequest` with `SendMessageConfiguration`; fixed in the packaged `agentbeats.client`.
- `fresh-live-20260818-210622` started the internal packaged A2A stack successfully, then failed when the debater process routed LiteLLM/Ollama traffic to local `localhost:11434` instead of an external Ollama Cloud endpoint.
- Gemini/Vertex defaults are now deployed for the fresh path: debaters use `vertex_ai/gemini-3.5-flash-lite`; judge and verifier use `vertex_ai/gemini-3.6-flash`.
- `fresh-gemini-live-20260818-212644` completed fresh cloud orchestration with the internal packaged A2A stack and Gemini/Vertex routes. The run did not produce an accepted sample because the judge returned `Failed to reach consensus` with `max_refinements=0`.
- `fresh-receipt-20260818-224627` produced a passing B-gate receipt and was promoted to GCS/Firestore.
- A later UI-selected `cve500:1` bounded live run completed but failed B-gate with `b_gate_not_passed`; this is a valid truthful outcome.
- Current safe revision is `barred-fleet-00038-skl`; live execution and promotion are disabled by default.

The remaining blocker is not model transport or basic promotion. It is production job control: durable async status, controlled seed source of truth, repeatable promotion policy, and operator-safe retry semantics.

### Goal

Move beyond curated report display by running bounded fresh debate jobs in cloud infrastructure with durable status and artifact provenance.

Detailed first-slice spec:

```text
docs/SPEC_BARRED_FLEET_FRESH_CLOUD_DEBATE.md
docs/SPEC_BARRED_FLEET_PACKAGED_DEBATE_RUNTIME.md
```

### Eventual Architecture

```text
POST /runs
  → validate seed/config
  → create pending run metadata
  → execute debate worker
  → write attempts/eval artifacts to GCS
  → update Firestore status
  → return run summary
```

For the first implementation, keep it synchronous and tiny:

- one seed;
- low row count;
- explicit model routes;
- timeout budget;
- temporary `/tmp` artifacts only;
- no queue.

Only after that works should it gain GCS writes, Firestore writes, and asynchronous execution.

### Tasks

1. Done: Add request schema for `POST /runs/fresh-demo`.
2. Done: Add dry-run mode that validates seed/config without calling models.
3. Done: Add a safe refusal path for non-dry-run execution while live mode is disabled.
4. Partial: Wire live execution hook behind `BARRED_ENABLE_LIVE_FRESH_DEBATE=true`.
5. Done: Add opt-in internal stack lifecycle manager.
6. Done: Package minimal reachable judge/pro/con/verifier runtime.
7. Pending: Run budget-approved live fresh debate and write temporary artifacts under `/tmp`.
8. Pending: Reuse deterministic B-gate/report assembly against those temp artifacts.
9. Pending: Defer GCS upload and Firestore write lifecycle to their dedicated phases.

### Test Gate

- Unit-test request validation.
- Unit-test dry-run.
- Unit-test artifact metadata creation.
- Manual live test with one tiny seed and strict budget.

### Acceptance

- A new run ID created in cloud can be reported in the fresh-run response.
- Deterministic B-gate still computes the acceptance decision.

## Phase 5 — Long-Running Async Jobs

### Goal

Support larger debates without blocking HTTP requests.

### Candidate Options

1. Cloud Run Jobs.
2. Pub/Sub-triggered Cloud Run worker.
3. Cloud Tasks.
4. Agent Runtime if the app moves to managed agent infrastructure.

### Recommended First Choice

Use Cloud Run Jobs or a Pub/Sub-triggered worker. Keep the existing API service separate from the worker if debate runs become slow or expensive.

### Tasks

1. Add Firestore run states:
   - `pending`
   - `running`
   - `succeeded`
   - `failed`
   - `rejected_by_gate`
2. Add status endpoint:
   - `GET /runs/<run_id>`
3. Add artifact lifecycle:
   - write partial logs;
   - write final attempts;
   - write deterministic eval;
   - update final metadata.
4. Add retry policy with idempotent run IDs.

### Test Gate

- Unit-test state transitions.
- Integration-test one queued run.
- Verify failed jobs leave useful metadata and logs.

## Phase 6 — Agent Gateway And Model Armor

### Goal

Add enterprise controls around ingress, egress, and unsafe raw inputs.

Detailed safety hardening map:

```text
docs/SPEC_BARRED_FLEET_MODEL_INPUT_SAFETY_HARDENING.md
docs/SPEC_BARRED_FLEET_MODEL_ARMOR_INTEGRATION_V1.md
```

### Scope Boundary

Do not claim these are implemented until configured and verified in Google Cloud.

### Agent Gateway Tasks

1. Decide whether BARRED-Fleet stays Cloud Run or moves to Agent Runtime.
2. Configure gateway only after the deployment target is stable.
3. Add egress policy for model/tool calls.
4. Verify logs show governed access.

### Model Armor Tasks

1. Identify untrusted text boundaries:
   - raw seeds;
   - generated attempts;
   - verifier outputs;
   - uploaded artifacts.
2. Add a pre-ingest screening step.
3. Log screening decisions.
4. Keep deterministic B-gate separate from content safety screening.

### Test Gate

- Unit-test that unsafe or malformed payloads fail closed.
- Manual cloud proof showing policy attached and active.

## Phase 7 — Reflection And Pareto Prompt Evolution

### Goal

Add controlled prompt/config improvement without undermining deterministic acceptance.

### Rule

Reflection can propose changes. Deterministic eval decides whether a candidate survives.

### Tasks

1. Define candidate prompt/config schema.
2. Run candidates against fixed evaluation seeds.
3. Track Pareto metrics:
   - accepted rows;
   - verifier pass rate;
   - parse OK rate;
   - B-gate pass;
   - cost;
   - latency;
   - unsupported/inconclusive rate.
4. Store candidate metadata, not huge generated bodies, in Firestore.
5. Keep rejected candidates auditable.

### Test Gate

- Fixed small eval set.
- No candidate can pass if B-gate fails.
- No candidate can silently improve one metric while violating acceptance constraints.

## Agent Execution Rules

For every implementation slice:

1. Start from `make verify-demo`.
2. Write or update a spec before code if behavior changes.
3. Add unit tests with fake cloud clients before live calls.
4. Keep local fallback working.
5. Run targeted tests.
6. Deploy only after explicit approval.
7. Run `make verify-demo` after deploy.
8. Update evidence docs with the new revision and exact result.

## Stop Conditions

Stop and ask before:

- broad IAM changes;
- public Cloud Run access;
- new paid cloud resources;
- live model calls that could consume material budget;
- deleting or replacing existing demo artifacts;
- changing the submitted repo after deadline.

## Recommended Next Engineering Slice After Submission

Implement Phase 2 first: GCS artifact upload lifecycle.

Reason: it is the smallest bridge from curated demo artifacts to real generated run artifacts. Firestore writes and fresh cloud debate execution become cleaner once artifact upload and hash verification are reliable.
