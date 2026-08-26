# Devpost Final Fields: BARRED-Fleet

## Project Name

BARRED-Fleet

## Tagline

Deterministic vulnerability acceptance reports and AST-guided GEPA optimization for multi-agent security debate.

## Short Description

BARRED-Fleet is a Google ADK + Cloud Run agent layer that turns multi-agent security-debate artifacts into deterministic, auditable vulnerability-acceptance reports, backed by an AST-guided GEPA optimizer delivering 66.3% token savings.

A user gives the deployed agent a short run ID or CVE target. The service resolves Firestore metadata, reads private GCS artifacts, executes deterministic B-gate checks, enforces verifier invariants, and generates official Google ADK CLI evaluation receipts (`agents-cli eval grade`/`compare`).

## Inspiration

AI security workflows can generate plausible vulnerability labels at scale, but acceptance is the dangerous step. A confident model answer is not enough if the artifact trail is unclear, verifier checks failed, anchors are weak, or replay artifacts are mistaken for live provider behavior.

Furthermore, generic LLM-as-optimizer approaches burn tens of thousands of tokens per reflection loop and hit rate limits on large codebase prompts without understanding program structure.

BARRED-Fleet focuses on that acceptance boundary: it shows what evidence was accepted, what was rejected, which model lanes participated, and whether deterministic gates passed before the result is allowed to become trusted signal.

## Market Context

Recent enterprise AI and agent-safety writing points to the same operational gap from different directions:

- IBM's 2026 breach research reports that AI-enabled attacks are changing breach economics by increasing attacker speed and scale, while security AI and automation can reduce breach impact when governed well.
- IBM's trust and governance principles emphasize transparency, explainability, and audit readiness for AI-assisted decisions.
- Anthropic's multiagent research describes coordination, conformity, epistemic, and conflicting-goal failures that can emerge when agents interact at scale.
- Jeff Crume's AI security-trilemma framing is a useful shorthand: capable, fast agents increase attack surface unless an external policy/control layer keeps inspection and enforcement in the loop.

BARRED-Fleet applies that lesson to vulnerability acceptance. Agents can debate, but a deterministic acceptance layer decides whether the evidence is strong enough to trust.

## What It Does

- Accepts a short BARRED run ID: e.g. `pilot-v1-calibrated-pecan` or security evaluation prompts.
- Resolves that run through Firestore metadata to private GCS artifacts.
- Materializes the artifacts inside Cloud Run for deterministic evaluation.
- Computes B-gate pass/fail using deterministic code, not model self-report.
- Shows accepted/rejected rows, verifier parse/pass rates, model routing, deterministic eval score, and artifact provenance.
- Uses Google Gemini in the cloud agent path: `gemini-3.6-flash` for the ADK root agent, and Vertex/Gemini defaults for bounded fresh debate (`vertex_ai/gemini-3.5-flash-lite` generator/debater, `vertex_ai/gemini-3.6-flash` judge/verifier).
- Integrates a **Graph-Powered GEPA Reflector** using local Tree-sitter AST data-flow extraction for **$0$-token diagnostics** and a **66.30% token reduction** on inference ($99,104 \rightarrow 33,401$ tokens per accepted row).
- Evaluates multiagent debates with official Google ADK CLI commands (`agents-cli eval grade` and `agents-cli eval compare`), maintaining a 100% self-contained trace and grading artifact suite.
- Preserves historical Ollama routing only as provenance for the curated pre-existing fixture.
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

- **Google ADK / `google-adk`**: Core agent architecture, multi-agent orchestration, and session state.
- **Google Agents CLI / `agents-cli`**: Evaluation suite execution (`agents-cli eval run`, `agents-cli eval grade`, `agents-cli eval compare`).
- **Google Cloud Run**: Serverless containerized deployment with dedicated service account.
- **Google Cloud IAM**: Dedicated runtime service account `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`.
- **Google Cloud Storage (GCS)**: Private storage bucket `gs://gem-creation-barred-fleet-artifacts` for run artifacts.
- **Firestore Native**: Named database `projects/gem-creation/databases/barred-fleet` for metadata index.
- **Cloud Logging / Trace**: Observability and telemetry.
- **Google Gemini 3.6 Flash**: Core ADK root agent model.
- **Vertex AI GenAI API**: Fresh debate execution with `vertex_ai/gemini-3.5-flash-lite` and `vertex_ai/gemini-3.6-flash`.
- **Google Cloud Model Armor**: Content and prompt screening receipts before live execution.
- **Google Agent Gateway / Network Services**: Egress route governance and policy receipts.

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

## Empirical Benchmark & Evaluation Receipts

A side-by-side evaluation was conducted comparing the **Unadapted Baseline**, the **Generic ADK Trace Optimizer**, and the **Graph-Powered GEPA Reflector** over 703 debate attempts and the 11-CVE benchmark suite:

```text
======================================================================
EMPIRICAL SIDE-BY-SIDE EVALUATION RECEIPT
======================================================================
1. Token Reduction (H_1,Y):        66.30% token reduction (99,104 -> 33,401 tokens/accept)
2. Diagnostic Cost:                0 LLM tokens (Tree-sitter AST data-flow extraction)
3. 1-Round Refinement Rescue:      71.4% (5/7 rescued in Round 1)
4. Verifier Logic Error Rate:      0.0000 (Zero contamination, INV-1 verified)
5. ADK CLI Graded Cases:           83 multi-round cases evaluated via agents-cli eval grade
6. Comparison Report:              docs/ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md
======================================================================
```

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
   - current Google model path: ADK root `gemini-3.6-flash`; bounded fresh defaults `vertex_ai/gemini-3.5-flash-lite` and `vertex_ai/gemini-3.6-flash`
   - historical curated-fixture routing: `ollama/gemma4:31b-cloud` and `ollama/gpt-oss:120b-cloud`
   - provenance chain: Firestore metadata → private GCS artifacts → deterministic B-gate → ADK narration
7. Show the fresh seed preview:
   - choose `cve500:N` or `fixture:first`
   - preview source file, index, language, safety label, and predicate hash
   - explain that bounded live execution is one attempt and requires server-side live flags
8. Show the ADK evaluation benchmark and the 66.3% token reduction documented in `ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md`.

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
ADK root route: gemini-3.6-flash
fresh generator/debater default: vertex_ai/gemini-3.5-flash-lite
fresh judge/verifier default: vertex_ai/gemini-3.6-flash
curated fixture generator/debater provenance: ollama/gemma4:31b-cloud
curated fixture judge/verifier provenance: ollama/gpt-oss:120b-cloud
```

## What Was Newly Built During The Hackathon

- `barred-fleet/` Google ADK app with full agent tool declarations.
- Cloud Run deployment target, Dockerfile, and FastAPI wrapper.
- Dedicated Cloud Run runtime identity with scoped permissions.
- Firestore-backed run-id metadata lookup.
- Private GCS-backed artifact resolution.
- Bounded seed selector for `fixture:first` and packaged `cve500:N` seeds.
- Product run lifecycle API: `POST /runs`, `GET /runs/{run_id}`, and `GET /runs/{run_id}/report`.
- Dry-run-first fresh debate UI with server-gated bounded live execution.
- Model Armor seed-screening receipt path and guaranteed-block smoke contract.
- Agent Gateway route/tool-egress receipt path and guaranteed-block smoke contract.
- Graph-Powered GEPA memory compiler and Pareto frontier loader (`app/gepa_memory.py`).
- Google ADK CLI evaluation benchmark (`tests/eval/eval_config_cve_ab.yaml`, `cve_sample_10_eval.json`).
- Complete ADK CLI grading and comparison receipts (`agents-cli eval grade` / `agents-cli eval compare`).
- Read-only `/demo`, `/demo/report`, `/seeds/manifest`, and `/memory/gepa/preview` surfaces.
- Deterministic report contract and unit/eval checks.
- Browser proof package, empirical comparison report, and demo script.

## Pre-Existing Work Disclosed

The local BARRED research harness, Agentbeats runtime primitives, replay/checkpoint logic, seed generation workflows, B-gate evaluator, and earlier pre-filter/graph experiments existed before this BARRED-Fleet cloud adapter.

This submission claims the new Google ADK + Cloud Run enterprise-agent layer, ADK evaluation benchmark suite, and cloud safety adapters around that harness.

## Challenges We Ran Into

- Keeping the demo honest: the cloud agent needed to narrate deterministic evidence, not pretend the LLM made the acceptance decision.
- Preserving local compatibility while adding Firestore and GCS resolution.
- Managing Vertex AI Tokens-Per-Minute (TPM) quota limits on massive Linux kernel C prompts by developing Tree-sitter AST data-flow slicing.
- Standardizing multi-round attempt traces into the official Google Agents CLI evaluation format.
- Keeping Cloud Run private while still capturing enough browser proof for judging.

## Accomplishments

- Deployed BARRED-Fleet to Cloud Run with a dedicated runtime service account and verified private IAM gating (unauthenticated `/demo` returns `403`).
- Built a Firestore metadata lookup and private GCS artifact reader behind a clean run-id interface.
- Demonstrated **66.30% token reduction** with **0 LLM diagnostic overhead** via Graph-Powered GEPA and verified with official `agents-cli eval grade` receipts across 83 cases.
- Implemented Model Armor and Agent Gateway pre-execution boundary receipts.
- Produced official HTML and JSON evaluation scorecards graded directly through the Google Agents CLI.

## What We Learned

The hard part is not generating more AI security examples. The hard part is deciding which outputs deserve to become accepted evidence and optimizing prompt evolution without burning quota on massive codebase prompts.

A neurosymbolic approach (combining deterministic Tree-sitter AST analysis with LLM multiagent debate) slashes prompt overhead by 66.3% and eliminates logic errors while keeping audit trails fully verifiable.

## What's Next

- Promote the current in-service `BackgroundTasks` async lifecycle to durable Cloud Tasks/Pub/Sub or a separate worker when runs become longer or higher volume.
- Promote seed source of truth from packaged `cve500:N` files to managed GCS objects after demo stability.
- Harden the current Agent Gateway egress receipt path into a fuller production policy with registered tools/agents.
- Expand the current Model Armor seed-screening path to additional artifact/output boundaries.
- Write redacted GEPA memory summaries to Firestore once the preview contract is stable.

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
barred-fleet/docs/DEMO_VIDEO_SCRIPT.md
```

Comparison report:
```text
barred-fleet/docs/ADK_OPTIMIZE_VS_GRAPH_GEPA_COMPARISON_REPORT.md
```

## Repository

```text
barred-fleet
```

This is the standalone submission repository. The broader Silver-One workspace is disclosed as the source of pre-existing BARRED research-harness components.
