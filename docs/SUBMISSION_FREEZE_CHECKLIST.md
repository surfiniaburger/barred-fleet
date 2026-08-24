# BARRED-Fleet Submission Freeze Checklist

## Purpose

Use this checklist immediately before Devpost submission and again immediately after submitting.

The goal is not more engineering. The goal is to avoid avoidable eligibility and reproducibility failures.

## Three Required Technical Criteria

| Requirement | Current Evidence | Status |
| --- | --- | --- |
| Gemini 3.5 or newer | BARRED-Fleet uses a Vertex/Gemini-compatible ADK configuration path. Verify final submission wording does not imply unsupported model claims. | Check before submit |
| Google agent framework | Google ADK / `google-adk` and Google Agents CLI / `agents-cli` are used in `barred-fleet/`. | Ready |
| Google Cloud service | Cloud Run service `barred-fleet`; Firestore metadata; private GCS artifacts. | Ready |

Do not submit until all three are actually visible in the text description, code, README, and/or demo video.

## Core Submission Fields

- [ ] Track/category selected.
- [ ] Project name is `BARRED-Fleet`.
- [ ] Tagline pasted from `docs/DEVPOST_FINAL_FIELDS.md`.
- [ ] Text description pasted or adapted from `docs/DEVPOST_FINAL_FIELDS.md`.
- [ ] Google technologies list includes ADK and Cloud Run.
- [ ] Firestore and GCS are mentioned as implemented cloud services.
- [ ] Pre-existing BARRED harness is disclosed.
- [ ] Startup Prize fields are blank or `N/A` unless submitting through a legally incorporated organization with corporate email.

## Demo Video Checklist

The video should be public on YouTube or Vimeo, not private. If unlisted is disallowed by the hackathon instructions, make it public.

Keep it under 4 minutes.

The video must show:

- [ ] Problem: AI vulnerability labels need deterministic acceptance gates.
- [ ] Value proposition: the agent explains a provenance-backed acceptance report.
- [ ] Cloud Run backend proof: Google Cloud Console, `.run.app` URL, or both.
- [ ] Service name: `barred-fleet`.
- [ ] Revision: `barred-fleet-00038-skl`.
- [ ] Runtime identity: `barred-fleet-runtime@gem-creation.iam.gserviceaccount.com`.
- [ ] Private access proof: unauthenticated `/demo` returns `403`.
- [ ] Authenticated `/demo` UI.
- [ ] Run-id-only prompt: `Report the BARRED run pilot-v1-calibrated-pecan in concise JSON.`
- [ ] B-gate `PASS`.
- [ ] Accepted rows `5 / 5`.
- [ ] Verifier parse OK `100%`.
- [ ] Verifier pass `75%`.
- [ ] Deterministic eval score `1.0`.
- [ ] Google model route is stated clearly: ADK root `gemini-3.6-flash`; bounded fresh defaults `vertex_ai/gemini-3.5-flash-lite` and `vertex_ai/gemini-3.6-flash`.
- [ ] Historical curated-fixture Ollama routes are labeled as provenance only, not the current Google model route.
- [ ] Provenance chain: Firestore metadata → private GCS artifacts → deterministic B-gate → ADK narration.
- [ ] Explicit boundary: LLM narrates; deterministic code decides acceptance.
- [ ] Fresh seed preview: `fixture:first` or `cve500:N` shows source, index, language, safety label, and predicate hash.
- [ ] Bounded live control: live execution is one attempt and server-flag gated, or safe refusal is shown when flags are off.

Use:

```text
barred-fleet/demo/DEMO_SCRIPT.md
```

as the narration source.

## Hosted URL Checklist

Hosted URL:

```text
https://barred-fleet-837262597425.us-east1.run.app/demo
```

Current posture:

```text
Private Cloud Run IAM access
```

If the hosted URL is private, include judge/testing access instructions in the Devpost testing instructions field. Do not put private credentials in the public description.

Minimum testing instruction:

```text
The Cloud Run demo is private by default. The video and screenshots show the deployed UI. If live access is required, contact the submitter for authorized Google account access or use the provided proof assets under barred-fleet/demo/.
```

If Devpost/Google requires direct access, share the private repo and service access only through the approved Devpost manager/judge path.

## Repository Checklist

- [ ] Repository link opens in incognito if public.
- [ ] If private, repository is shared with the required hackathon emails:
  - `testing@devpost.com`
  - `cloudhackathons@google.com`
- [ ] README includes setup commands.
- [ ] README includes Cloud Run proof.
- [ ] README includes bounded fresh selector/run explanation.
- [ ] README includes disclosures.
- [ ] README does not claim fresh selected seeds always pass B-gate.
- [ ] README does not claim Memory Bank, Agent Registry, or long-running Agent Runtime are implemented. Model Armor and Agent Gateway are described only as safety/egress receipt paths.
- [ ] Demo assets are present under `barred-fleet/demo/`.
- [ ] Final screenshot is present:

  ```text
  barred-fleet/demo/Screenshot 2026-08-18 at 00.55.23.png
  ```

- [ ] Demo script is present:

  ```text
  barred-fleet/demo/DEMO_SCRIPT.md
  ```

- [ ] Final Devpost fields are present:

  ```text
  docs/DEVPOST_FINAL_FIELDS.md
  ```

## Architecture Diagram Checklist

At minimum, include the diagram from `docs/DEVPOST_FINAL_FIELDS.md` or `barred-fleet/README.md`.

The architecture should show:

```text
User / ADK agent
Cloud Run /demo and /demo/report
POST /runs/fresh-demo
report_barred_run tool
Firestore metadata
Private GCS artifacts
Deterministic B-gate
bounded seed selector
Auditable report
```

Do not use an architecture diagram that implies:

- fresh selected seeds always pass B-gate;
- Agent Gateway is currently attached;
- Model Armor is currently screening inputs;
- Agent Runtime is the deployed target.

## Final Verification Commands

Run from:

```bash
cd /Users/surfiniaburger/Desktop/modular-metacog-swarm-v3/agent_training/silver-one/barred-fleet
```

Required:

```bash
make verify-demo
```

Expected:

- private `/demo` check passes with `403`;
- authenticated `/demo/report` contract passes;
- ADK smoke prompt calls `report_barred_run`;
- B-gate passes.

Optional local tests:

```bash
make test-unit
```

If `uv` fails due to local cache permissions, do not treat that as application failure without checking the specific error.

## Proof Assets Checklist

Current proof index:

```text
barred-fleet/demo/README.md
```

Expected proof assets:

- [ ] `Screenshot 2026-08-18 at 00.55.23.png`
- [ ] `Screen Recording 2026-08-17 at 14.46.46.mov`
- [ ] Cloud Run service/revision screenshot
- [ ] Runtime identity/security screenshot
- [ ] ADK run-id-only prompt screenshot or terminal capture

## Disclosure Checklist

State clearly:

- [ ] The local BARRED research harness existed before the hackathon.
- [ ] Agentbeats runtime primitives existed before the hackathon.
- [ ] Existing seed generation, replay, checkpoint, verifier, and B-gate logic existed before the hackathon.
- [ ] Earlier graph/prefilter experiments existed before the hackathon and are not part of the deployed demo claim.
- [ ] New hackathon work is the `barred-fleet/` ADK + Cloud Run adapter, Firestore/GCS resolution, read-only demo UI, deterministic report contract, and proof package.

This disclosure protects eligibility better than vague language. Do not hide the pre-existing work.

## No-Overclaim Checklist

Before submitting, search the final text for claims that imply:

- [ ] fresh selected seeds always pass B-gate;
- [ ] graph/prefilter is used in the deployed demo result;
- [ ] cassette replay is provider-side cache telemetry;
- [ ] Model Armor decides vulnerability acceptance;
- [ ] Agent Gateway decides vulnerability acceptance;
- [ ] Memory Bank is implemented;
- [ ] Agent Registry is implemented;
- [ ] Agent Runtime is the deployment target;
- [ ] LLMs decide B-gate acceptance.

If any are present, rewrite them as roadmap items or remove them.

## Startup Prize Decision

Only fill Startup Prize organization/email fields if submitting on behalf of a legally incorporated organization.

Owning a domain and email address is not enough by itself.

If not incorporated:

```text
N/A
```

or leave the fields blank if optional.

## Post-Submission Freeze

After the deadline:

- [ ] Do not edit the submitted repo.
- [ ] Do not replace the demo video.
- [ ] Do not change linked docs or hosted proof materials.
- [ ] Do not make new commits to the submitted branch.
- [ ] Do not mutate screenshots or evidence files.

If continuing development:

```text
Fork the repo or move BARRED-Fleet into a new repo after submission.
```

Recommended post-submission first slice:

```text
GCS artifact upload lifecycle.
```

Then:

```text
Firestore write lifecycle → fresh cloud debate execution → async jobs → Model Armor/Gateway hardening → reflection/Pareto prompt evolution.
```

## Final Human Review

Before clicking submit:

- [ ] Open the repo link in incognito.
- [ ] Open the video link in incognito.
- [ ] Confirm the architecture diagram is uploaded.
- [ ] Confirm all teammates accepted invites.
- [ ] Confirm the hosted URL/testing instructions are clear.
- [ ] Confirm disclosures are included.
- [ ] Confirm the project satisfies ADK + Gemini 3.5+ + Google Cloud service requirements.
- [ ] Run `make verify-demo` one last time.
