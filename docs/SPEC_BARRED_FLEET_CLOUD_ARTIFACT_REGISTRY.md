# Spec: BARRED-Fleet Cloud Artifact Registry

## Objective

Move BARRED-Fleet from a hardcoded packaged demo run toward a cloud-ready run registry without breaking the local demo flow.

The user-facing contract remains unchanged:

```text
Report the BARRED run <run_id> in concise JSON.
```

The implementation resolves `<run_id>` to artifact metadata, materializes any remote artifacts needed by deterministic tools, computes B-gate locally inside the service, and returns the same report schema used by the deployed demo.

## Tech Stack

- Python `>=3.11`
- Google ADK / `agents-cli`
- Cloud Run
- `gcsfs` for `gs://` artifact reads
- Optional `google.cloud.firestore` import for Firestore registry lookup
- Existing deterministic BARRED B-gate code under `scenarios/debate/offline_b_gate.py`

## Commands

```bash
cd barred-fleet
uv run pytest tests/unit -q
make demo-smoke
agents-cli deploy --project gem-creation --region us-east1 --service-account barred-fleet-runtime@gem-creation.iam.gserviceaccount.com --min-instances 0 --max-instances 1 --concurrency 1 --no-confirm-project
```

Authenticated report check:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -H "Authorization: Bearer ${TOKEN}" "https://barred-fleet-837262597425.us-east1.run.app/demo/report?run_id=pilot-v1-calibrated-pecan"
```

## Project Structure

```text
barred-fleet/app/run_registry.py
  Resolves run IDs from local JSON, optional GCS JSON, and optional Firestore documents.

barred-fleet/app/tools.py
  Materializes local or GCS artifact paths before deterministic summary/B-gate/eval processing.

barred-fleet/barred_runtime/run_registry.json
  Local packaged fallback registry for the current demo run.

barred-fleet/tests/unit/test_run_registry.py
  Registry source and validation tests.

barred-fleet/tests/unit/test_tools.py
  Report/B-gate artifact materialization tests.
```

## Code Style

Keep adapters small, explicit, and fail-closed:

```python
artifacts = resolve_run_artifacts(
    run_id,
    registry_path=RUN_REGISTRY_PATH,
    registry_uri=RUN_REGISTRY_URI,
    firestore_collection=RUN_REGISTRY_FIRESTORE_COLLECTION,
)
```

Rules:

- Environment variables select cloud adapters.
- No cloud adapter is enabled by default.
- Local JSON remains the default fallback.
- Remote artifacts are staged to `/tmp` before passing paths to deterministic BARRED code.
- Invalid registry fields raise `ValueError`; unknown run IDs return `attention_required`.

## Testing Strategy

- Unit-test registry validation with local temp files.
- Unit-test GCS registry loading with injected fake readers.
- Unit-test Firestore document loading with injected fake readers.
- Unit-test `gs://` artifact materialization by monkeypatching the downloader.
- Do not require live Google Cloud calls in unit tests.
- Live Cloud Run smoke remains manual/explicit because it consumes deployed infrastructure.

## Boundaries

- Always: Preserve `report_barred_run(run_id=...)` and local packaged demo behavior.
- Always: Keep unknown run IDs non-throwing at `/demo/report`; return `attention_required`.
- Always: Keep deterministic B-gate computation local to the deployed service.
- Ask first: Provision buckets, create Firestore collections, add IAM bindings, or deploy.
- Ask first: Add new runtime dependencies beyond what `pyproject.toml` already includes.
- Never: Commit credentials, embed project-specific secrets, or make Cloud Run public by default.

## Success Criteria

- Local registry-backed demo still passes unit tests.
- `gs://` artifact paths can be materialized behind existing summary/B-gate/eval functions.
- Firestore registry lookup can be enabled through environment variables without changing the agent/tool API.
- If cloud registry is absent or disabled, the deployed demo still resolves `pilot-v1-calibrated-pecan`.
- Unknown run IDs return a structured `attention_required` report rather than a 500.

## Deployment Evidence

- Bucket: `gs://gem-creation-barred-fleet-artifacts`
- Registry object: `gs://gem-creation-barred-fleet-artifacts/registry/run_registry.json`
- Firestore database: `projects/gem-creation/databases/barred-fleet`
- Firestore collection/document: `barred_runs/pilot-v1-calibrated-pecan`
- Cloud Run revision: `barred-fleet-00025-zs6`
- Runtime reader: `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`
- Runtime bucket role: `roles/storage.objectViewer`
- Runtime Firestore role: conditional `roles/datastore.viewer` limited to `projects/gem-creation/databases/barred-fleet`
- Smoke result: `pilot-v1-calibrated-pecan` resolves through Firestore to `gs://` corpus, attempts, and deterministic eval artifacts; B-gate passes.

## Open Questions

- Whether artifact uploads should be performed by a separate ingest job, Cloud Run admin endpoint, or local CLI script.
