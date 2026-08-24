# BARRED-Fleet 4-Minute Demo Video Script

Target length: `3:35–3:55`. Devpost evaluates only the first four minutes.

## Verification Boundary

`make verify-demo` should stay deterministic. It should prove the deployed agent can resolve cloud artifacts, enforce private access, call the ADK tool path, and return the curated B-gate PASS report.

Do not make `make verify-demo` toggle Cloud Run live-debate flags, run paid model calls, then toggle them back. That creates cost risk, leaves infrastructure state brittle if the command is interrupted, and makes the core proof path non-repeatable.

Use a separate opt-in command or manual clip for live fresh debate:

1. Enable `BARRED_ENABLE_LIVE_FRESH_DEBATE=true`.
2. Enable `BARRED_START_INTERNAL_DEBATE_STACK=true`.
3. Keep `BARRED_MAX_LIVE_FRESH_ATTEMPTS=1`.
4. Run one selected `fixture:first` or `cve500:N` seed.
5. Return the service to the closed/default posture.

The main judged proof should be deterministic; the live run is bonus evidence if time and budget allow.

## Recording Checklist

- Browser tab with `/demo` screenshot or temporarily authenticated `/demo`.
- Google Cloud Console tab showing Cloud Run service `barred-fleet`.
- Cloud Run revision/service-account/security screenshot ready.
- Terminal in `barred-fleet/`.
- Optional: `docs/DEVPOST_SUBMISSION_DRAFT.md` open for reference.

## Script

### 0:00–0:20 — Hook

**Screen:** BARRED-Fleet `/demo` UI.

**Narration:**

> This is BARRED-Fleet. Enterprise AI is running into a security trilemma: capable agents are useful, fast agents are valuable, but both increase the need for inspection and control. In vulnerability workflows, the hard problem is not generating labels with AI. The hard problem is knowing which generated decisions are trustworthy enough to accept.

### 0:20–0:50 — Problem And Product

**Screen:** `/demo` top cards: B-gate, accepted rows, verifier parse/pass.

**Narration:**

> A model can sound confident and still be unsupported. Recent multiagent research shows that agent coordination and epistemic failures do not disappear just because models get stronger. IBM's breach research also points to the same enterprise pressure: AI changes attacker speed and scale, so defenders need governed automation. BARRED-Fleet separates narration from governance: the model explains the report, but deterministic tools compute the B-gate, verifier rates, artifact provenance, and model routing.

### 0:50–1:25 — Cloud Proof

**Screen:** Google Cloud Console, Cloud Run service `barred-fleet`.

**Narration:**

> This is deployed on Google Cloud Run as `barred-fleet` in `us-east1`. The validated revision is `barred-fleet-00038-skl`. It runs with a dedicated runtime identity, `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`, rather than relying on a broad default identity. The service was temporarily public for browser proof capture and then returned to IAM-required private access.

### 1:25–2:05 — Agent Flow

**Screen:** Terminal running:

```bash
cd barred-fleet
make demo-smoke
```

**Narration:**

> The user does not need to know internal artifact paths. The prompt is just: “Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.” The ADK agent calls `report_barred_run`, resolves the known run ID to curated artifacts, and returns the deterministic report.

### 2:05–2:45 — Result

**Screen:** Terminal result or `/demo` result cards.

**Narration:**

> For this run, B-gate passes. There are five accepted rows from seventeen attempts, with twelve rejected attempts preserved as evidence. Verifier parse-ok rate is one hundred percent, verifier pass rate is seventy-five percent, and the deterministic eval contract scores one point zero. The model routing shows asymmetric debate: Gemma handled generation/debate calls, while GPT-OSS handled judge and verifier lanes.

### 2:45–3:15 — Fresh Bounded Path

**Screen:** Fresh Debate Seed Preview panel.

**Narration:**

> The demo also includes a bounded fresh-debate path. I can choose `fixture:first` or an indexed `cve500` seed, preview the source file, index, language, safety label, and predicate hash, and only then request a one-attempt live run. Server-side flags still gate live execution. A fresh run can pass or fail B-gate; the point is that the acceptance result is computed and visible.

### 3:15–3:35 — Architecture

**Screen:** README architecture Mermaid or simple diagram.

**Narration:**

> Architecturally, this is an ADK and Cloud Run adapter over a disclosed existing BARRED research harness. The new hackathon work is the BARRED-Fleet cloud layer: ADK tool wiring, Cloud Run deployment, scoped identity, run-id artifact registry, bounded seed selector, deterministic report contract, and browser demo surface. The underlying local debate harness is disclosed as prior research infrastructure.

### 3:35–3:50 — Boundaries And Roadmap

**Screen:** README disclosure/limitations or Devpost draft.

**Narration:**

> The current validated report is curated and stable, while fresh runs are bounded and may fail B-gate. That boundary is intentional and disclosed. The next production steps are GCS seed storage, async jobs, broader Model Armor screening, fuller Agent Gateway policy enforcement, and reflection-driven prompt evolution.

### 3:50–3:58 — Close

**Screen:** `/demo` UI final view.

**Narration:**

> BARRED-Fleet is a security-control layer for multi-agent vulnerability debate: less handholding, clearer provenance, and deterministic acceptance gates before AI-generated security claims become trusted data.

## Must-Show Evidence

- Cloud Run URL or service page.
- Revision `barred-fleet-00038-skl`.
- Runtime service account `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`.
- `make verify-demo` or `make demo-smoke` plus authenticated `/demo/report`.
- B-gate `PASS`.
- Accepted rows `5`.
- Attempt rows `17`, with `12` rejected attempts preserved.
- Verifier parse OK `100%`.
- Verifier pass `75%`.
- Deterministic eval score `1.0`.
- Fresh seed preview with `fixture:first` or `cve500:N`.
- Bounded live control or safe refusal if live flags are disabled.
- Disclosure that local BARRED harness is pre-existing and BARRED-Fleet is the new cloud/ADK adapter.

## Optional Live Fresh Clip

Only include this if it is already captured cleanly. Do not spend the main demo budget waiting on live model calls.

**Narration:**

> This live path is intentionally not part of `make verify-demo`. The deterministic verification command must be cheap, repeatable, and safe to run under a closed Cloud Run posture. Live fresh debate is separately gated because it can spend model budget and may produce either a B-gate pass or fail.

If shown, capture:

- selected seed ID and metadata preview;
- one-attempt cap;
- live flags enabled before the run;
- B-gate pass or fail;
- service returned to private/default posture after the run.

## Do Not Claim

- Do not claim the whole BARRED harness was built from scratch for the hackathon.
- Do not claim fresh selected seeds always pass B-gate.
- Do not claim Memory Bank, Agent Registry, or long-running Agent Runtime are implemented. Model Armor and Agent Gateway are safety/egress receipt paths, not vulnerability-acceptance authorities.
- Do not claim graph/prefilter lift from this demo.
- Do not describe cassette replay as provider-side cache telemetry.
