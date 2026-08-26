# BARRED-Fleet

BARRED-Fleet is a Google ADK + Cloud Run adapter for an auditable multi-agent security-reasoning harness.

It turns a disclosed existing BARRED research workflow into a cloud-hosted enterprise-agent demo surface: one short run ID resolves to deterministic artifacts, B-gate status, verifier metrics, model routing, deterministic eval results, and provenance notes.

## Problem

AI-generated security labels are cheap to produce and expensive to trust. A model can claim a vulnerability is real, but a security team still needs to know:

- what evidence anchored the claim,
- which model roles were involved,
- whether a verifier audited the mechanism,
- whether weak or unsupported outputs were rejected,
- whether the final acceptance decision came from deterministic governance rather than model self-report.

BARRED-Fleet makes that acceptance layer visible.

## The BARRED Swarm Methodology

Building upon the foundational Plural AI multi-agent debate research (**BARRED**: *Boundary Adversarial Reasoning for Reproducible Evaluation and Decision*), `BARRED-Fleet` surfaces the six architectural pillars of the expanded **BARRED-Swarm** (*Boundary-Aware Reflective Robust Exploration & Decision*):

| Letter | Architectural Component | Role in the Swarm |
| :--- | :--- | :--- |
| **B** | **Boundary-Aware** | Extracts vulnerability dimensions (CVE predicates, boundary conditions, reachability constraints) and synthesizes edge-case code samples. |
| **A** | **Asymmetric** | Orchestrates opposing purple agents (Pro-Attacker vs. Con-Defender) supervised by a green judge to eliminate hallucinated consensus. |
| **R** | **Reflective** | Executes iterative refinement via the GEPA Reflector (reflective meta-prompt mutation and diagnostic triage across refinement rounds). |
| **R** | **Robust** | Enforces deterministic quality floors via the B-Gate (AST parse coverage, strict anchor grounding, zero logic errors, and parse reliability). |
| **E** | **Exploration** | Drives stratified, scenario-grouped cross-validation across holdouts to ensure zero data leakage between train/test partitions. |
| **D** | **Debate & Decision** | Produces verified, high-fidelity vulnerability acceptance decisions and auditable security evaluation reports to govern code-security guardrails. |

## What This Demo Shows

The deployed demo has two modes:

1. **Curated report mode** for `pilot-v1-calibrated-pecan`.
2. **Bounded fresh-run mode** for `fixture:first` or packaged `cve500:N` seeds.

It reports:

- B-gate pass/fail.
- Accepted and rejected attempt counts.
- Verifier parse/pass rates.
- Google Gemini routing: the ADK root agent uses `gemini-3.6-flash`; bounded fresh runs default to `vertex_ai/gemini-3.5-flash-lite` for generation/debate and `vertex_ai/gemini-3.6-flash` for judge/verifier roles.
- Historical model provenance: the curated fixture preserves its original `ollama/gemma4:31b-cloud` and `ollama/gpt-oss:120b-cloud` routing as artifact evidence, not as the current Google model route.
- Deterministic eval score and deterministic receipt presence.
- Provenance chain: Firestore metadata → private GCS artifacts → deterministic B-gate → ADK narration.
- Product run lifecycle: `POST /runs`, `GET /runs/{run_id}`, and `GET /runs/{run_id}/report`.
- Seed manifest and bounded selector: `/seeds/manifest`, `fixture:first`, and `cve500:N` only.
- Model Armor seed-screening receipt and Agent Gateway route/tool-egress receipt before live execution.
- Read-only GEPA memory preview at `/memory/gepa/preview` for redacted historical reflector evidence.
- Artifact provenance and cache-telemetry caveat.

The demo prompt is intentionally short:

```text
Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.
```

The agent resolves the known run through a run registry without requiring the user to provide internal artifact paths. The deployed service now uses Firestore metadata pointing to private GCS artifacts; the GCS registry JSON and packaged local registry remain fallbacks.

Cloud registry inputs are supported behind the same run-id interface:

```text
BARRED_RUN_REGISTRY_GCS_URI=gs://gem-creation-barred-fleet-artifacts/registry/run_registry.json
BARRED_RUN_REGISTRY_FIRESTORE_COLLECTION=barred_runs
BARRED_RUN_REGISTRY_FIRESTORE_PROJECT=gem-creation
BARRED_RUN_REGISTRY_FIRESTORE_DATABASE=barred-fleet
BARRED_GCS_ARTIFACT_CACHE_DIR=/tmp/barred-fleet-artifacts
```

Resolution order is Firestore document, GCS registry JSON, local registry JSON, then packaged demo fixture fallback. Artifacts referenced with `gs://` are materialized to the local cache before deterministic B-gate/eval code reads them.

## Product API Surface

BARRED-Fleet exposes a small product-shaped API around the demo runtime:

| Route | Purpose | Live model call |
| --- | --- | --- |
| `GET /demo` | Browser demo surface. | No |
| `GET /demo/report?run_id=...` | Curated artifact-backed report for the demo UI. | No |
| `GET /seeds/manifest` | Allowlisted seed source counts and SHA-256 digests. | No |
| `POST /runs` | Product lifecycle wrapper for dry-run or bounded fresh run requests. | Only when live flags are enabled |
| `POST /runs/fresh-demo` | Backward-compatible demo wrapper over the same fresh-run planner/executor. | Only when live flags are enabled |
| `GET /runs/{run_id}` | Durable run status from Firestore/local registry. | No |
| `GET /runs/{run_id}/report` | Artifact-backed product report when artifacts exist; diagnostic report when blocked/planned. | No |
| `GET /memory/gepa/preview` | Redacted GEPA/Pareto memory preview. | No |

The report path is intentionally read-only. It never triggers a fresh debate, never mutates Cloud Run flags, and never treats missing artifacts for planned/blocked runs as a model failure.

## Safety And Governance Boundaries

BARRED-Fleet separates three decisions that should not be collapsed:

- **Model Armor** screens selected seed text before live execution. Its authority is `content_safety_only`.
- **Agent Gateway** checks model route/tool egress policy before live execution. Its authority is `routing_and_egress_only`.
- **B-gate** is the only vulnerability-acceptance authority. It decides whether generated evidence is accepted.

A Model Armor pass or Agent Gateway pass never means a vulnerability claim is accepted. It only means the run may proceed to the bounded debate runtime.

## Google Cloud Proof

Cloud Run service:

```text
service: barred-fleet
region: us-east1
project: gem-creation
validated safe UI revision: barred-fleet-00038-skl
runtime service account: barred-fleet-runtime@gem-creation.iam.gserviceaccount.com
demo URL: https://barred-fleet-837262597425.us-east1.run.app/demo
artifact bucket: gs://gem-creation-barred-fleet-artifacts
metadata database: projects/gem-creation/databases/barred-fleet
metadata collection: barred_runs
ADK root model: gemini-3.6-flash
fresh debate defaults: vertex_ai/gemini-3.5-flash-lite + vertex_ai/gemini-3.6-flash
```

Security posture:

- The service was temporarily made public to capture browser proof.
- After capture, public access was removed.
- Unauthenticated `/demo` access returned `HTTP/2 403`.
- Authenticated ADK calls still work with `agents-cli run`.
- Firestore resolves `pilot-v1-calibrated-pecan` to private `gs://` artifacts.

Captured proof is indexed in `demo/README.md`.

## Agent Handoff Docs

For future agents or post-submission continuation:

- `docs/BARRED_FLEET_AGENT_HANDOFF.md` records the current deployed state, verification commands, IAM/GCS/Firestore details, and failure recovery notes.
- `docs/BARRED_FLEET_ROADMAP_EXECUTION_PLAN.md` sequences the post-submission roadmap from GCS upload lifecycle through fresh cloud debate execution and reflection/Pareto evolution.
- `docs/SUBMISSION_FREEZE_CHECKLIST.md` captures the Devpost lock checklist, disclosure requirements, and no-overclaim rules.
- `docs/BARRED_FLEET_ARCHITECTURE.md` contains the one-page demo architecture diagram and path-by-path explanation.

## Architecture

![BARRED-Fleet System Architecture](docs/architecture_diagram.png)

```mermaid
flowchart LR
    User["User / Judge"] --> Demo["/demo UI"]
    User --> ADK["agents-cli run"]
    Demo --> DemoReport["GET /demo/report"]
    Demo --> ProductRun["POST /runs"]
    Demo --> FreshCompat["POST /runs/fresh-demo"]
    Demo --> SeedManifest["GET /seeds/manifest"]
    Demo --> MemoryPreview["GET /memory/gepa/preview"]
    ADK --> RootAgent["Google ADK root_agent"]
    RootAgent --> Tool["report_barred_run"]
    DemoReport --> Tool
    Tool --> Registry["Firestore / GCS / packaged registry"]
    Registry --> Corpus["Corpus JSONL"]
    Registry --> Attempts["Attempts JSONL"]
    Registry --> Eval["Deterministic eval receipt"]
    Corpus --> BGate["Offline deterministic B-gate"]
    Attempts --> BGate
    Eval --> BGate
    BGate --> Report["Acceptance report"]
    ProductRun --> Selector["Bounded seed selector"]
    FreshCompat --> Selector
    Selector --> Seeds["fixture:first or cve500:N"]
    ProductRun --> Safety["Model Armor + Agent Gateway receipts"]
    Safety --> LiveGate["Live flags + max_attempts<=1"]
    LiveGate --> Runtime["Packaged debate runtime"]
    Runtime --> BGate
    ProductRun --> Status["GET /runs/{run_id}"]
    ProductRun --> ProductReport["GET /runs/{run_id}/report"]
    ProductReport --> Report
```

The LLM narrates the report. The B-gate decision is computed by deterministic code.

## Hackathon Disclosure

This project is not claiming that the entire BARRED research harness was created from scratch during the hackathon.

Pre-existing work reused:

- Local BARRED debate scenario under `../scenarios/debate/`.
- Existing Agentbeats runtime primitives under `../src/agentbeats/`.
- Existing corpus generation, replay, checkpoint, verifier, and offline B-gate logic.
- Earlier seed-expansion, pre-filter, graph-extractor, and evaluation docs/experiments.

New hackathon work:

- This `barred-fleet/` Google ADK project.
- Cloud Run deployment target and packaged demo runtime.
- Dedicated Cloud Run runtime identity.
- Run-id-only artifact resolution for the curated demo run.
- Bounded seed selector for `fixture:first` and packaged `cve500:N` seeds.
- Product run lifecycle routes: `POST /runs`, `GET /runs/{run_id}`, and `GET /runs/{run_id}/report`.
- Gated fresh-debate endpoint and UI controls with dry-run-first behavior.
- Model Armor seed-screening receipts and Agent Gateway egress-policy receipts before live execution.
- Read-only `/demo`, `/demo/report`, `/seeds/manifest`, and `/memory/gepa/preview` surfaces.
- ADK eval/report fixtures and deterministic report contract.
- Demo evidence package.

## Current Limitations

- The primary validated result remains the curated BARRED run `pilot-v1-calibrated-pecan`.
- The fresh-debate path is bounded for demo safety: dry-run preview first, `max_attempts=1`, and live execution only when `BARRED_ENABLE_LIVE_FRESH_DEBATE=true` and `BARRED_START_INTERNAL_DEBATE_STACK=true`.
- A fresh selected seed can legitimately fail B-gate; that is a truthful result, not a UI failure.
- Graph/prefilter behavior is intentionally optional and not part of the demo claim.
- Model Armor and Agent Gateway are implemented as guarded safety/egress receipt paths; they do not decide vulnerability acceptance.
- GEPA memory is preview-only and redacted; prompt mutation/self-evolution is not enabled in Cloud Run.
- In-service async lifecycle exists through FastAPI `BackgroundTasks` for `POST /runs` with `async_mode=true`; external durable queueing via Cloud Tasks/Pub/Sub/separate workers is not implemented yet.
- Memory Bank, Agent Registry, and long-running Agent Runtime deployment are not implemented yet. Cloud Run remains the deployment target.
- Cassette replay is local deterministic replay evidence, not provider-side prompt/KV cache telemetry.

## Local Setup

Prerequisites:

- Python `>=3.11`
- `uv`
- Google Cloud SDK
- `agents-cli`

Install Agents CLI if needed:

```bash
uv tool install google-agents-cli
uvx google-agents-cli setup
```

Install dependencies:

```bash
cd barred-fleet
agents-cli install
```

Run unit tests:

```bash
make test-unit
```

Expected current result:

```text
140 passed
```

## Demo Commands

Authenticated cloud smoke:

```bash
make demo-smoke
```

Equivalent explicit command:

```bash
agents-cli run \
  --url https://barred-fleet-837262597425.us-east1.run.app \
  --mode adk \
  "Report the BARRED run pilot-v1-calibrated-pecan in concise JSON."
```

Local deterministic eval grading:

```bash
make eval-report-grade-deterministic
```

Run ADK CLI benchmark evaluation & comparison:

```bash
# Grade the Graph-GEPA multi-round suite (83 cases)
agents-cli eval grade \
  --traces artifacts/traces/graph_gepa_multi_round_traces.json \
  --config tests/eval/eval_config_cve_ab.yaml \
  --output artifacts/grade_results/graph_gepa_graded/

# Run side-by-side comparison with baseline
agents-cli eval compare \
  artifacts/grade_results/baseline_new/results_20260826_004955.json \
  artifacts/grade_results/graph_gepa_graded/results_20260826_011010.json
```

Browser demo path:

```text
https://barred-fleet-837262597425.us-east1.run.app/demo
```

The browser route requires authentication when Cloud Run is private.

Fresh-debate and safety verification:

```bash
make verify-fresh-demo
```

This verifies `POST /runs/fresh-demo` planning, safe live refusal, Model Armor seed-screening receipts, and Agent Gateway pass/block receipts without spending on a live model call.

Product lifecycle verification:

```bash
make verify-product-run
```

This verifies `POST /runs`, `GET /runs/{run_id}`, and `GET /runs/{run_id}/report` in dry-run mode.

GEPA memory preview verification:

```bash
make gepa-memory-preview-local
make gepa-memory-preview-smoke
```

These verify the redacted GEPA memory preview locally and against the authenticated Cloud Run service.

Fresh-debate selector examples:

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -sS \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -X POST \
  "https://barred-fleet-837262597425.us-east1.run.app/runs/fresh-demo" \
  -d '{"seed_id":"cve500:0","run_id":"seed-selector-cloud-smoke","dry_run":true,"max_attempts":1}'
```

Expected dry-run result:

```text
status: planned
seed_metadata.source: cve500
seed_metadata.source_file: scenarios/debate/cve_seeds_500.jsonl
```

Live bounded execution is intentionally opt-in:

```text
BARRED_ENABLE_LIVE_FRESH_DEBATE=true
BARRED_START_INTERNAL_DEBATE_STACK=true
BARRED_MAX_LIVE_FRESH_ATTEMPTS=1
```

Keep those flags off unless recording a bounded live proof.

Packaged internal debate stack verification:

```bash
make verify-packaged-stack
```

This starts the packaged judge/pro/con/verifier localhost A2A services, verifies the judge becomes reachable, then confirms cleanup. It does not run model inference.

## Deployment

Deploy to Cloud Run:

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

The deploy command uses private access by default via `--no-allow-unauthenticated`.

## Demo Script

1. Show the Cloud Run service and revision in Google Cloud Console.
2. Show runtime identity `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`.
3. Run `make demo-smoke` or the explicit `agents-cli run` command.
4. Open `/demo` while authenticated or show the captured browser recording.
5. Explain that the user provides only a run ID; BARRED-Fleet resolves artifacts and computes B-gate results.
6. Point out the provenance chain, accepted rows, verifier parse/pass rates, model routing, deterministic eval score, and provenance note.
7. Show seed preview and bounded live control; explain that live execution is server-flag gated and a fresh run may pass or fail B-gate.
8. Close with limitations and roadmap: async jobs, artifact lifecycle hardening, managed memory/registry exploration, and reflection/Pareto prompt evolution.

## Files To Review

- `app/agent.py`: ADK root agent and tool registration.
- `app/run_registry.py`: Firestore/GCS/local run-id to artifact resolver.
- `app/run_lifecycle.py`: product run lifecycle and artifact-backed report aggregation.
- `app/fresh_debate.py`: bounded seed selection, dry-run planning, and live-gated fresh execution.
- `app/model_armor.py`: Model Armor receipt boundary for seed/artifact screening.
- `app/agent_gateway.py`: Agent Gateway receipt boundary for route/tool egress policy.
- `app/gepa_memory.py`: redacted GEPA/Pareto memory preview compiler.
- `app/tools.py`: deterministic BARRED report and B-gate adapters.
- `app/demo.py`: read-only demo report and HTML rendering.
- `app/fast_api_app.py`: FastAPI routes, ADK app wrapper, and Cloud Run entry point.
- `barred_runtime/run_registry.json`: packaged curated run registry.
- `tests/unit/test_tools.py`: deterministic adapter tests.
- `tests/unit/test_run_registry.py`: run registry resolver tests.
- `tests/unit/test_demo.py`: demo surface tests.
- `demo/README.md`: captured proof index.

## License

Apache License 2.0. See `LICENSE`.
