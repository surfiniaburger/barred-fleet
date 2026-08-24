# BARRED-Fleet Demo Evidence

This folder contains captured proof for the BARRED-Fleet Cloud Run demo path.

Use `DEMO_SCRIPT.md` for the final recorded walkthrough. It separates shipped claims from roadmap claims.

## Current Cloud Proof

| Item | Evidence |
| --- | --- |
| Cloud Run service | `barred-fleet` in project `gem-creation`, region `us-east1`. |
| Validated revision | `barred-fleet-00038-skl`. |
| Runtime identity | `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`. |
| Demo URL | `https://barred-fleet-837262597425.us-east1.run.app/demo`. |
| Access posture | Private again; unauthenticated `/demo` returned `HTTP/2 403`. |
| Fresh execution posture | Bounded seed preview is deployed; live execution remains disabled unless both server-side live flags are enabled. |
| Metadata source | Firestore Native named database `projects/gem-creation/databases/barred-fleet`, collection `barred_runs`. |
| Artifact source | Private GCS bucket `gs://gem-creation-barred-fleet-artifacts`. |
| Demo run ID | `pilot-v1-calibrated-pecan`. |
| Deterministic result | B-gate `PASS`, `5/5` accepted, verifier parse OK `100%`, verifier pass `75%`, deterministic eval score `1.0`. |

## Assets

| File | Evidence |
| --- | --- |
| `Screenshot 2026-08-18 at 00.55.23.png` | Final authenticated `/demo` browser proof after the provenance-chain UI update, including `Provenance Chain` and `Decision Breakdown`. |
| `Screenshot 2026-08-18 at 00.25.53.png` | Fresh authenticated `/demo` browser proof after the final provenance-chain UI update. |
| Local screen recording | Captured locally for editing/upload, but intentionally not committed to keep the repository small. The public Devpost video should be hosted on YouTube or Vimeo. |
| `Screenshot 2026-08-17 at 14.17.44.png` | Cloud Run hosted UI at the `barred-fleet-837262597425.us-east1.run.app` URL. |
| `Screenshot 2026-08-17 at 14.33.11.png` | Deployed Cloud Run service/revision evidence for BARRED-Fleet. |
| `Screenshot 2026-08-17 at 14.34.36.png` | Scoped runtime/service identity or Cloud Run security configuration evidence. |
| `Screenshot 2026-08-17 at 14.36.19.png` | Run-id-only ADK prompt and deterministic BARRED report result evidence. |

## What The Evidence Proves

- BARRED-Fleet is deployed on Google Cloud Run.
- The deployed service can render a browser-readable product demo.
- The ADK agent can answer the short prompt: `Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.`
- The short prompt resolves to curated artifacts without requiring internal artifact paths from the user.
- The fresh seed preview accepts only `fixture:first` or `cve500:N` seed IDs and shows metadata before any live run.
- The bounded live-debate button is deployed, but the backend refuses live execution unless server-side flags permit it.
- Deterministic B-gate passes for the demo fixture.
- The report shows accepted/rejected rows, verifier parse/pass rates, model routing, deterministic eval score, and artifact provenance.

## Current Provenance Chain

The latest deployed demo makes the chain explicit in the UI:

1. Firestore stores only run metadata for `pilot-v1-calibrated-pecan`.
2. That metadata resolves private GCS artifact URIs.
3. The Cloud Run service materializes those artifacts into `/tmp` at runtime.
4. The deterministic B-gate verifies the artifact-backed run.
5. The ADK agent narrates the result from the deterministic report.

This matters for the hackathon demo because the user prompt is run-id-only, not path-handheld. The service proves it can retrieve, verify, and explain the run from cloud metadata and private artifacts.

## Fresh Bounded Path

The `/demo` surface also includes a fresh-debate control path:

1. Select `fixture:first` or an allowlisted `cve500:N` seed.
2. Run a dry-run preview that returns seed metadata without calling a paid model.
3. Optionally request a bounded live run.
4. The backend permits live execution only when `BARRED_ENABLE_LIVE_FRESH_DEBATE=true`, `BARRED_START_INTERNAL_DEBATE_STACK=true`, and the request stays within the configured one-attempt cap.

This path is intentionally separate from the curated PASS report. A fresh selected seed can pass or fail B-gate; the demo must describe that outcome truthfully.

## Repro Commands

From `barred-fleet/`:

```bash
make verify-demo
```

This runs the private access check, authenticated `/demo/report` contract check, and deployed ADK smoke prompt.

Individual checks:

```bash
make demo-smoke
```

Authenticated report check:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "https://barred-fleet-837262597425.us-east1.run.app/demo/report?run_id=pilot-v1-calibrated-pecan"
```

Private access check:

```bash
curl -I https://barred-fleet-837262597425.us-east1.run.app/demo
```

Expected unauthenticated result: `HTTP/2 403`.

## Privacy Posture

The service was temporarily made public to capture browser proof. After capture, public access was removed and unauthenticated `/demo` access returned `HTTP/2 403`.
