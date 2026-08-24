# BARRED-Fleet Demo Script

Target length: 2-3 minutes.

## Core Claim

BARRED-Fleet is a Google ADK + Cloud Run agent layer that turns a BARRED multi-agent security-debate run into a deterministic, auditable vulnerability-acceptance report.

The important point is not that an LLM says "accept." The important point is that the deployed agent can take a short run ID, resolve the right cloud artifacts, run deterministic checks, and explain the result with provenance.

## What To Show

1. Cloud Run service `barred-fleet` in project `gem-creation`, region `us-east1`.
2. Latest validated revision `barred-fleet-00038-skl`.
3. Runtime service account `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`.
4. Private access posture: unauthenticated `/demo` returns `HTTP/2 403`.
5. Authenticated `/demo` browser page.
6. The short prompt:

   ```text
   Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.
   ```

7. The dashboard cards:
   - B-gate `PASS`
   - accepted rows `5 / 5`
   - verifier parse OK `100%`
   - verifier pass `75%`
   - decision breakdown
   - asymmetric debate routing
   - deterministic eval score `1.0`
   - provenance chain
8. Fresh Debate Seed Preview:
   - seed source `fixture:first` or `cve500:N`
   - selected seed metadata
   - bounded live-debate control
   - safe backend refusal when live flags are disabled

## Spoken Walkthrough

### 0:00-0:20 — Problem

"Security teams should not trust AI-generated vulnerability labels just because a model sounds confident. BARRED-Fleet focuses on the acceptance decision: what was accepted, what was rejected, which models were involved, and whether the final result passed deterministic checks."

### 0:20-0:45 — Cloud Agent Surface

"This is the deployed Cloud Run service for BARRED-Fleet. It is running as a dedicated service identity, and the browser demo is private again after proof capture. The public URL exists, but unauthenticated access returns 403."

### 0:45-1:20 — Run-Id-Only Handoff

"The user does not provide internal file paths. The prompt is only: report the BARRED run `pilot-v1-calibrated-pecan`. The ADK agent resolves that run through Firestore metadata, then reads private GCS artifacts."

### 1:20-1:55 — Deterministic Acceptance

"The B-gate is deterministic. For this demo run it passes: 5 accepted out of 5 total accepted rows, verifier parse OK is 100%, verifier pass rate is 75%, and the deterministic eval contract score is 1.0. The model is not deciding these numbers; it is narrating computed facts."

### 1:55-2:25 — Asymmetric Debate And Provenance

"The artifact records show asymmetric model routing: the generation/debate lane used `ollama/gemma4:31b-cloud`, while judge and verifier work used `ollama/gpt-oss:120b-cloud`. The provenance chain is Firestore metadata, private GCS artifacts, deterministic B-gate, then ADK narration."

### 2:25-2:45 — Fresh Bounded Path

"The deployed UI also has a fresh-debate path. It starts with an allowlisted seed selector such as `fixture:first` or `cve500:1`, shows metadata first, and keeps live execution behind server-side flags and a one-attempt cap. Fresh runs are allowed to fail B-gate; that is part of the safety posture."

### 2:45-3:05 — Boundary And Roadmap

"This submission does not claim the full BARRED research harness was created during the hackathon. The new work is the ADK and Cloud Run enterprise-agent layer, private artifact resolution, deterministic report contract, bounded fresh-debate control path, and browser demo. Next steps are production async jobs, Agent Gateway, Model Armor, and a larger cloud debate execution lifecycle."

## Commands To Show If Needed

```bash
cd barred-fleet
make demo-smoke
```

```bash
TOKEN="$(gcloud auth print-identity-token)"
curl -sS -H "Authorization: Bearer ${TOKEN}" \
  "https://barred-fleet-837262597425.us-east1.run.app/demo/report?run_id=pilot-v1-calibrated-pecan"
```

```bash
curl -I https://barred-fleet-837262597425.us-east1.run.app/demo
```

Expected unauthenticated result:

```text
HTTP/2 403
```

## Do Not Overclaim

- Do not claim the full local BARRED harness was built during the hackathon.
- Do not claim fresh selected seeds always pass B-gate.
- Do not claim graph/prefilter work is part of the deployed demo result.
- Do not claim cassette replay is provider-side cache telemetry.
- Do not claim Memory Bank, Agent Registry, or long-running Agent Runtime are implemented. Model Armor and Agent Gateway are safety/egress receipt paths, not vulnerability-acceptance authorities.
- Do not claim the LLM decides acceptance; deterministic code computes B-gate acceptance.

## One-Sentence Close

"BARRED-Fleet turns multi-agent vulnerability debate output into a cloud-hosted, provenance-backed acceptance report where the agent explains the result but deterministic gates decide whether the evidence is acceptable."
