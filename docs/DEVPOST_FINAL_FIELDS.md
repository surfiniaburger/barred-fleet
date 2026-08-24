# Devpost Final Fields: BARRED-Fleet

## Project Name

BARRED-Fleet

## Tagline

Deterministic vulnerability acceptance reports for multi-agent security debate.

## Short Description

BARRED-Fleet is a Google ADK + Cloud Run agent layer that turns multi-agent security-debate artifacts into deterministic, auditable vulnerability-acceptance reports.

A user gives the deployed agent a short run ID. The service resolves Firestore metadata, reads private GCS artifacts, runs deterministic B-gate checks, reports verifier health, exposes asymmetric model routing, and renders the evidence chain in a browser demo.

## Inspiration

AI security workflows can generate plausible vulnerability labels at scale, but acceptance is the dangerous step. A confident model answer is not enough if the artifact trail is unclear, verifier checks failed, anchors are weak, or replay artifacts are mistaken for live provider behavior.

BARRED-Fleet focuses on that acceptance boundary: it shows what evidence was accepted, what was rejected, which model lanes participated, and whether deterministic gates passed before the result is allowed to become trusted signal.

## Market Context

Recent enterprise AI and agent-safety writing points to the same operational gap from different directions:

- IBM's 2026 breach research reports that AI-enabled attacks are changing breach economics by increasing attacker speed and scale, while security AI and automation can reduce breach impact when governed well.
- IBM's trust and governance principles emphasize transparency, explainability, and audit readiness for AI-assisted decisions.
- Anthropic's multiagent research describes coordination, conformity, epistemic, and conflicting-goal failures that can emerge when agents interact at scale.
- Jeff Crume's AI security-trilemma framing is a useful shorthand: capable, fast agents increase attack surface unless an external policy/control layer keeps inspection and enforcement in the loop.

BARRED-Fleet applies that lesson to vulnerability acceptance. Agents can debate, but a deterministic acceptance layer decides whether the evidence is strong enough to trust.

## What It Does

- Accepts a short BARRED run ID: `pilot-v1-calibrated-pecan`.
- Resolves that run through Firestore metadata to private GCS artifacts.
- Materializes the artifacts inside Cloud Run for deterministic evaluation.
- Computes B-gate pass/fail using deterministic code, not model self-report.
- Shows accepted/rejected rows, verifier parse/pass rates, model routing, deterministic eval score, and artifact provenance.
- Provides product-shaped run routes: `POST /runs`, `GET /runs/{run_id}`, and `GET /runs/{run_id}/report`.
- Lets a reviewer choose `fixture:first` or `cve500:N`, preview bounded seed metadata, and run a one-attempt live debate only when server-side live flags are explicitly enabled.
- Exposes `/seeds/manifest` so seed sources are allowlisted and digest-auditable.
- Screens seed input with Model Armor before live execution when configured.
- Checks route/tool egress with an Agent Gateway receipt before live execution.
- Exposes a read-only redacted GEPA memory preview at `/memory/gepa/preview`.
- Provides a read-only `/demo` UI and `/demo/report` JSON endpoint.
- Keeps the Cloud Run service private after proof capture; unauthenticated `/demo` returns `HTTP/2 403`.

## How We Built It

We wrapped an existing BARRED local research harness with a new Google ADK project called `barred-fleet`.

The deployed Cloud Run service exposes a compact product API:

- `/demo`: browser-readable proof surface for judges.
- `/demo/report`: JSON report endpoint used by the UI and by the ADK agent tool path.
- `/seeds/manifest`: allowlisted seed sources, counts, and SHA-256 digests.
- `/runs`: product lifecycle wrapper for dry-run or bounded fresh debate.
- `/runs/fresh-demo`: backward-compatible demo wrapper for `fixture:first` and packaged `cve500:N` seeds.
- `/runs/{run_id}`: durable run status.
- `/runs/{run_id}/report`: artifact-backed product report or blocked/planned diagnostic report.
- `/memory/gepa/preview`: redacted GEPA/Pareto memory preview.

The ADK root agent calls `report_barred_run` with only a run ID. The tool resolves run metadata from Firestore, reads private GCS artifacts, runs deterministic B-gate checks, and returns a report. The LLM narrates the computed result; it does not decide acceptance.

## Google Technologies Used

- Google ADK / `google-adk`
- Google Agents CLI / `agents-cli`
- Google Cloud Run
- Google Cloud IAM with a dedicated runtime service account
- Google Cloud Storage for private run artifacts
- Firestore Native named database for run metadata
- Cloud Logging / Trace-ready deployment configuration
- Vertex/Gemini-compatible ADK configuration path
- Google Cloud Model Armor for configured seed-screening receipts
- Google Agent Gateway / Network Services egress-governance resource and local policy adapter

## External Context Links

- IBM Cost of a Data Breach 2026 newsroom summary: `https://newsroom.ibm.com/2026-07-29-ibm-study-one-in-four-malicious-breaches-are-ai-enabled%2C-costing-companies-6-million-on-average`
- IBM Trust and Transparency principles: `https://www.ibm.com/policy/blog/trust-principles`
- IBM AI governance discussion: `https://www.ibm.com/think/insights/from-principles-to-actions-building-a-holistic-approach-to-ai-governance`
- Anthropic Responsible Scaling Policy: `https://www.anthropic.com/responsible-scaling-policy`

## Cloud Proof

```text
Cloud Run service: barred-fleet
Project: gem-creation
Region: us-east1
Validated revision: barred-fleet-00038-skl
Runtime identity: barred-fleet-runtime@gem-creation.iam.gserviceaccount.com
Demo URL: https://barred-fleet-837262597425.us-east1.run.app/demo
Artifact bucket: gs://gem-creation-barred-fleet-artifacts
Metadata database: projects/gem-creation/databases/barred-fleet
Metadata collection: barred_runs
```

The service was temporarily public only for browser proof capture, then returned to private IAM-required access. Unauthenticated `/demo` returned `HTTP/2 403` after the privacy reset.

## Demo Script

1. Show the Cloud Run service `barred-fleet`.
2. Show revision `barred-fleet-00038-skl` and runtime identity `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`.
3. Show private access posture: unauthenticated `/demo` returns `HTTP/2 403`.
4. Open authenticated `/demo`.
5. Show the run-id-only prompt:

   ```text
   Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.
   ```

6. Show the dashboard:
   - B-gate: `PASS`
   - accepted rows: `5 / 5`
   - verifier parse OK: `100%`
   - verifier pass: `75%`
   - deterministic eval score: `1.0`
   - asymmetric model routing: `ollama/gemma4:31b-cloud` and `ollama/gpt-oss:120b-cloud`
   - provenance chain: Firestore metadata → private GCS artifacts → deterministic B-gate → ADK narration
7. Show the fresh seed preview:
   - choose `cve500:N` or `fixture:first`
   - preview source file, index, language, original safety, and predicate hash
   - explain that bounded live execution is one attempt and requires server-side live flags

## Results From Demo Fixture

```text
run_id: pilot-v1-calibrated-pecan
B-gate: passed
accepted rows: 5
attempt rows: 17
rejected attempts: 12
verifier parse-ok rate: 1.0
verifier pass rate: 0.75
deterministic eval mean score: 1.0
generator/debater route: ollama/gemma4:31b-cloud
judge/verifier route: ollama/gpt-oss:120b-cloud
```

## What Was Newly Built During The Hackathon

- `barred-fleet/` Google ADK app.
- Cloud Run deployment target and FastAPI wrapper.
- Dedicated Cloud Run runtime identity.
- Firestore-backed run-id metadata lookup.
- Private GCS-backed artifact resolution.
- Bounded seed selector for `fixture:first` and packaged `cve500:N` seeds.
- Product run lifecycle API: `POST /runs`, `GET /runs/{run_id}`, and `GET /runs/{run_id}/report`.
- Dry-run-first fresh debate UI with server-gated bounded live execution.
- Model Armor seed-screening receipt path and guaranteed-block smoke contract.
- Agent Gateway route/tool-egress receipt path and guaranteed-block smoke contract.
- Redacted GEPA memory preview surface.
- Read-only `/demo`, `/demo/report`, `/seeds/manifest`, and `/memory/gepa/preview` surfaces.
- Deterministic report contract and unit/eval checks.
- Browser proof package and demo script.

## Pre-Existing Work Disclosed

The local BARRED research harness, Agentbeats runtime primitives, replay/checkpoint logic, seed generation workflows, B-gate evaluator, and earlier pre-filter/graph experiments existed before this BARRED-Fleet cloud adapter.

This submission claims the new Google ADK + Cloud Run enterprise-agent layer around that harness, not that the entire research harness was built from scratch during the hackathon.

## Challenges We Ran Into

- Keeping the demo honest: the cloud agent needed to narrate deterministic evidence, not pretend the LLM made the acceptance decision.
- Preserving local compatibility while adding Firestore and GCS resolution.
- Keeping Cloud Run private while still capturing enough browser proof for judging.
- Avoiding overclaiming around replay artifacts, graph/prefilter experiments, and roadmap-only Google Cloud services.
- Making the evidence understandable in a short demo without handholding the service with local artifact paths.

## Accomplishments

- Deployed BARRED-Fleet to Cloud Run with a dedicated runtime service account.
- Verified private Cloud Run access: authenticated demo works, unauthenticated `/demo` returns `403`.
- Added Firestore metadata lookup and private GCS artifact reads behind a short run-id interface.
- Added product run lifecycle routes and artifact-backed report enrichment.
- Added Model Armor and Agent Gateway receipt boundaries before live execution.
- Added a browser dashboard that shows B-gate status, verifier rates, model routing, deterministic eval, safety receipts, and provenance.
- Verified the ADK smoke prompt calls the deployed `report_barred_run` tool and returns the expected deterministic report.

## What We Learned

The hard part is not generating more AI security examples. The hard part is deciding which outputs deserve to become accepted evidence. A useful enterprise agent needs provenance, deterministic gates, model-route visibility, and honest boundaries between model narration and computed facts.

Safety controls are deliberately scoped: Model Armor handles content-safety screening, Agent Gateway handles route/tool-egress governance, and deterministic B-gate remains the only vulnerability-acceptance authority.

## What's Next

- Move synchronous bounded fresh runs to async cloud jobs with clearer queued/running/completed transitions.
- Promote seed source of truth from packaged `cve500:N` files to managed GCS objects after demo stability.
- Harden the current Agent Gateway egress receipt path into a fuller production policy with registered tools/agents.
- Expand the current Model Armor seed-screening path to additional artifact/output boundaries.
- Write redacted GEPA memory summaries to Firestore once the preview contract is stable.
- Evaluate Agent Runtime, Memory Bank, Agent Registry, and richer observability once the core Cloud Run adapter is stable.

## Demo Assets

Evidence is indexed in:

```text
barred-fleet/demo/README.md
```

Primary final screenshot:

```text
barred-fleet/demo/Screenshot 2026-08-18 at 00.55.23.png
```

Demo script:

```text
barred-fleet/demo/DEMO_SCRIPT.md
```

## Repository

```text
barred-fleet
```

This is the standalone submission repository. The broader Silver-One workspace is disclosed as the source of pre-existing BARRED research-harness components.
