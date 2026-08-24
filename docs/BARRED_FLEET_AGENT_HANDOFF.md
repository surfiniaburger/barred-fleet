# BARRED-Fleet Agent Handoff

## Purpose

This document lets a future agent continue BARRED-Fleet without relying on chat history.

BARRED-Fleet is the hackathon-facing Google ADK + Cloud Run adapter around the existing BARRED local security-debate harness. It does not claim the full BARRED harness was newly built during the hackathon. The new claim is the enterprise-agent layer: run-id-only artifact resolution, private cloud artifacts, deterministic B-gate reporting, ADK narration, and browser proof.

## Current Shipped State

```text
Cloud Run service: barred-fleet
Project: gem-creation
Region: us-east1
Service URL: https://barred-fleet-837262597425.us-east1.run.app
Latest validated revision: barred-fleet-00038-skl
Runtime identity: barred-fleet-runtime@gem-creation.iam.gserviceaccount.com
Demo run ID: pilot-v1-calibrated-pecan
```

The service is private. Authenticated requests work; unauthenticated `/demo` returns `HTTP/2 403`.

## Google Cloud State

### Cloud Run

- Service: `barred-fleet`
- Region: `us-east1`
- Project: `gem-creation`
- Revision validated after bounded live-control UI polish: `barred-fleet-00038-skl`
- Runtime service account: `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`
- Intended access posture: private Cloud Run IAM, not public.

### GCS

- Bucket: `gs://gem-creation-barred-fleet-artifacts`
- Registry object: `gs://gem-creation-barred-fleet-artifacts/registry/run_registry.json`
- Demo artifact objects:
  - `gs://gem-creation-barred-fleet-artifacts/runs/pilot-v1-calibrated-pecan/training_corpus_calibrated_pecan.jsonl`
  - `gs://gem-creation-barred-fleet-artifacts/runs/pilot-v1-calibrated-pecan/artifacts/attempts/pilot-v1-calibrated-pecan.jsonl`
  - `gs://gem-creation-barred-fleet-artifacts/runs/pilot-v1-calibrated-pecan/barred-fleet/tests/fixtures/pecan_demo/deterministic_eval_result.json`
- Runtime service account role: `roles/storage.objectViewer`.

### Firestore

- Database: `projects/gem-creation/databases/barred-fleet`
- Mode: Firestore Native named database.
- Collection: `barred_runs`
- Demo document: `barred_runs/pilot-v1-calibrated-pecan`
- Stored data: artifact metadata and URIs only; do not store large corpus bodies or code snippets in Firestore.
- Runtime service account role: conditional `roles/datastore.viewer` scoped to `projects/gem-creation/databases/barred-fleet`.

Do not replace this with broad unconditioned project-level datastore permissions unless explicitly approved. The scoped binding is intentional.

## Runtime Environment Variables

The deployed service expects these cloud registry variables:

```text
BARRED_RUN_REGISTRY_GCS_URI=gs://gem-creation-barred-fleet-artifacts/registry/run_registry.json
BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION=barred_runs
BARRED_RUN_REGISTRY_FIRESTORE_PROJECT=gem-creation
BARRED_RUN_REGISTRY_FIRESTORE_DATABASE=barred-fleet
BARRED_GCS_ARTIFACT_CACHE_DIR=/tmp/barred-fleet-artifacts
```

Resolution order:

1. Firestore run document.
2. GCS registry JSON.
3. Local registry JSON.
4. Packaged demo fixture fallback.

This order is important: local development must keep working without cloud adapters, while deployed Cloud Run should prefer Firestore metadata.

## Key Files

```text
barred-fleet/app/agent.py
  ADK root agent definition.

barred-fleet/app/tools.py
  report_barred_run tool, GCS artifact materialization, B-gate/eval report assembly.

barred-fleet/app/run_registry.py
  Local JSON, GCS JSON, and Firestore run metadata resolution.

barred-fleet/app/demo.py
  Read-only /demo HTML and /demo/report JSON shaping.

barred-fleet/app/fresh_debate.py
  Fresh-debate request validation, bounded seed selection, dry-run planning, and opt-in live runner hook.

barred-fleet/app/debate_stack.py
  Opt-in subprocess lifecycle manager for starting the packaged localhost A2A debate stack.

barred-fleet/app/fast_api_app.py
  FastAPI app exposing ADK, demo, and `POST /runs/fresh-demo` routes.

barred-fleet/Makefile
  test-unit, demo-smoke, verify-demo, verify-fresh-demo, and eval helper commands.

barred-fleet/demo/
  Screenshot/video proof, demo script, and evidence README.

docs/DEVPOST_FINAL_FIELDS.md
  Paste-ready Devpost content.

docs/SPEC_BARRED_FLEET_CLOUD_ARTIFACT_REGISTRY.md
  Current cloud artifact registry specification and evidence.

docs/SPEC_BARRED_FLEET_FRESH_CLOUD_DEBATE.md
  First-slice specification for fresh Cloud Run debate execution.

docs/SPEC_BARRED_FLEET_PACKAGED_DEBATE_RUNTIME.md
  Concrete stack-manager specification for packaging and starting judge/pro/con/verifier services.

docs/SPEC_BARRED_FLEET_BOUNDED_SEED_SELECTOR.md
  Selector specification for `fixture:first` and packaged `cve500:N` seeds.

docs/BARRED_FLEET_ARCHITECTURE.md
  One-page architecture diagram for the current submission path and fresh bounded path.
```

## Core Verification Commands

From:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
```

Run the full deployed demo verification:

```bash
make verify-demo
```

This checks:

- unauthenticated `/demo` returns `403`;
- authenticated `/demo/report` returns `200`;
- JSON contract reports `status=ok`, B-gate pass, `5/5`, verifier parse OK `1.0`, verifier pass `0.75`, deterministic eval score `1.0`, and Firestore provenance;
- deployed ADK smoke prompt calls `report_barred_run`.

Run focused local unit tests:

```bash
make test-unit
```

Run the deployed fresh-debate dry-run verification:

```bash
make verify-fresh-demo
```

This checks authenticated `POST /runs/fresh-demo` dry-run planning and confirms non-dry-run execution refuses safely unless `BARRED_ENABLE_LIVE_FRESH_DEBATE=true`.

The `/demo` UI also exposes a bounded live button. It stays disabled until a seed preview succeeds. Live execution requires both:

```text
BARRED_ENABLE_LIVE_FRESH_DEBATE=true
BARRED_START_INTERNAL_DEBATE_STACK=true
```

The default live cap is one attempt:

```text
BARRED_MAX_LIVE_FRESH_ATTEMPTS=1
```

Run the packaged stack manager checks:

```bash
uv run pytest tests/unit/test_debate_stack.py tests/unit/test_fresh_debate.py -q
make verify-packaged-stack
```

If `uv` fails with permission errors against `/Users/surfiniaburger/.cache/uv`, rerun with proper local permissions or from an environment that can read the uv cache. Do not change application code to work around a local uv cache permission problem.

Run the ADK smoke path directly:

```bash
make demo-smoke
```

Expected prompt:

```text
Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.
```

Expected high-level result:

```text
status: ok
B-gate: passed
accepted rows: 5
total rows: 5
verifier parse OK: 1.0
verifier pass: 0.75
deterministic eval score: 1.0
```

## Deploy Command

Deploy the current `barred-fleet` app to Cloud Run:

```bash
agents-cli deploy \
  --project gem-creation \
  --region us-east1 \
  --service-account barred-fleet-runtime@gem-creation.iam.gserviceaccount.com \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 1 \
  --no-confirm-project
```

The deploy path uses private access by default. Do not add public unauthenticated access except temporarily for recording, and reset it immediately after proof capture.

## Known Good Deployment Checks

Authenticated `/demo`:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -sS -o /tmp/barred-demo.html -w '%{http_code}\n' \
  -H "Authorization: Bearer ${TOKEN}" \
  https://barred-fleet-837262597425.us-east1.run.app/demo
```

Expected: `200`.

Authenticated `/demo/report`:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "https://barred-fleet-837262597425.us-east1.run.app/demo/report?run_id=pilot-v1-calibrated-pecan"
```

Expected:

- `status` is `ok`;
- `b_gate.passed` is `true`;
- `provenance.chain[0].system` starts with `Firestore metadata:`;
- artifact paths use `gs://gem-creation-barred-fleet-artifacts`.

Unauthenticated `/demo`:

```bash
curl -I https://barred-fleet-837262597425.us-east1.run.app/demo
```

Expected: `HTTP/2 403`.

## Demo Evidence

Proof folder:

```text
barred-fleet/demo/
```

Primary proof files:

```text
barred-fleet/demo/README.md
barred-fleet/demo/DEMO_SCRIPT.md
barred-fleet/demo/Screenshot 2026-08-18 at 00.55.23.png
barred-fleet/demo/Screen Recording 2026-08-17 at 14.46.46.mov
```

The final screenshot should show the deployed `/demo` surface with `Provenance Chain` and `Decision Breakdown`.

## Do Not Overclaim

Do not claim:

- the entire local BARRED research harness was created during the hackathon;
- fresh selected seeds always pass B-gate;
- graph/prefilter experiments are part of the deployed demo result;
- cassette replay is provider-side cache telemetry;
- Memory Bank, Agent Registry, or long-running Agent Runtime are implemented; Model Armor and Agent Gateway are safety/egress receipt paths, not vulnerability-acceptance authorities;
- the LLM decides vulnerability acceptance.

Correct claim:

```text
The ADK agent narrates computed facts. Deterministic BARRED code computes the B-gate acceptance result.
```

## Common Failure Modes

### `gcloud info --run-diagnostics` cannot resolve Google APIs

Likely local DNS/network issue. Validate:

```bash
dig cloudresourcemanager.googleapis.com
dig iam.googleapis.com
curl -I https://cloudresourcemanager.googleapis.com
```

If local DNS fails but `dig @8.8.8.8 iam.googleapis.com` works, fix the local resolver before retrying deploy/IAM commands.

### Cloud Run returns `403`

This is expected for unauthenticated browser or curl access. Use:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -H "Authorization: Bearer ${TOKEN}" ...
```

`agents-cli run --url ... --mode adk` handles authenticated remote agent calls.

### `/demo/report` fails to resolve artifacts

Check environment variables first:

- `BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION`
- `BARRED_RUN_REGISTRY_FIRESTORE_PROJECT`
- `BARRED_RUN_REGISTRY_FIRESTORE_DATABASE`
- `BARRED_RUN_REGISTRY_GCS_URI`

Then confirm the runtime service account can read:

- Firestore database `barred-fleet`;
- bucket `gs://gem-creation-barred-fleet-artifacts`.

### `uv run` fails due to uv cache permission

This is local environment friction, not necessarily a code failure. Do not refactor code to hide cache permission errors.

### ADK smoke returns blank or non-tool answer

Check `barred-fleet/app/agent.py` and tool descriptions. The current known-good behavior is a `report_barred_run({"run_id": "pilot-v1-calibrated-pecan"})` tool call followed by JSON narration.

## Submission Freeze Rule

After Devpost deadline, do not edit the submitted repo, swap the video, or change linked materials until winners are announced. If more work is needed after submission, fork or create a new repo and continue there.
