from __future__ import annotations

import html
from typing import Any

from app.invariant_scorecard import build_invariant_scorecard
from app.tools import (
    RUN_REGISTRY_FIRESTORE_COLLECTION,
    RUN_REGISTRY_FIRESTORE_DATABASE,
    RUN_REGISTRY_FIRESTORE_PROJECT,
    RUN_REGISTRY_URI,
    report_barred_run,
)

DEMO_RUN_ID = "pilot-v1-calibrated-pecan"
DEMO_PROMPT = f"Report the BARRED run {DEMO_RUN_ID} in concise JSON."


def build_demo_report(run_id: str = DEMO_RUN_ID) -> dict[str, Any]:
    report = report_barred_run(run_id=run_id)
    selected_metrics = report.get("b_gate", {}).get("selected_metrics") or {}
    attempts = (
        report.get("artifact_summary", {})
        .get("artifacts", {})
        .get("attempts", {})
    )
    deterministic_eval = (report.get("eval_results", {}).get("deterministic") or {})
    summary_metrics = deterministic_eval.get("summary_metrics") or []
    deterministic_score = (
        summary_metrics[0].get("mean_score")
        if summary_metrics and isinstance(summary_metrics[0], dict)
        else None
    )

    return {
        "run_id": report.get("run_id"),
        "status": report.get("status"),
        "demo_prompt": f"Report the BARRED run {run_id} in concise JSON.",
        "b_gate": {
            "status": report.get("b_gate", {}).get("status"),
            "passed": report.get("b_gate", {}).get("passed"),
            "failed_checks": report.get("b_gate", {}).get("failed_checks", []),
            "error": report.get("b_gate", {}).get("error"),
            "selected_metrics": selected_metrics,
            "invariant_scorecard": build_invariant_scorecard(selected_metrics),
            "accepted_rows": selected_metrics.get("accepted_rows"),
            "total_rows": selected_metrics.get("total_rows"),
            "verifier_parse_ok_rate": selected_metrics.get("verifier_parse_ok_rate"),
            "verifier_pass_rate": selected_metrics.get("verifier_pass_rate"),
            "anchor_match_rate": selected_metrics.get("b2_anchor_match_rate"),
        },
        "attempts": {
            "row_count": attempts.get("row_count"),
            "decisions": attempts.get("decisions", {}),
            "verifier": attempts.get("verifier", {}),
        },
        "model_routing": report.get("model_routing", {}),
        "deterministic_eval": {
            "exists": deterministic_eval.get("exists"),
            "score": deterministic_score,
            "summary_metrics": summary_metrics,
        },
        "model_armor": report.get("model_armor") or {"status": "not_configured"},
        "agent_gateway": report.get("agent_gateway") or {"status": "not_configured"},
        "provenance": {
            "artifact_paths": report.get("artifact_paths", {}),
            "artifact_registry": report.get("artifact_registry", {}),
            "chain": _build_provenance_chain(report),
            "notes": report.get("notes", []),
        },
    }


def _build_provenance_chain(report: dict[str, Any]) -> list[dict[str, str]]:
    artifact_paths = report.get("artifact_paths", {})
    has_gcs_artifacts = any(
        str(path).startswith("gs://") for path in artifact_paths.values()
    )
    metadata_source = _metadata_source_label()
    artifact_source = (
        "Private GCS artifacts" if has_gcs_artifacts else "Packaged local artifacts"
    )

    return [
        {
            "step": "1. Run metadata",
            "system": metadata_source,
            "evidence": str(report.get("run_id") or ""),
        },
        {
            "step": "2. Artifact storage",
            "system": artifact_source,
            "evidence": str(artifact_paths.get("input_path") or "unresolved"),
        },
        {
            "step": "3. Deterministic gate",
            "system": "BARRED offline B-gate",
            "evidence": "pass" if report.get("b_gate", {}).get("passed") else "not-pass",
        },
        {
            "step": "4. Agent role",
            "system": "ADK root agent",
            "evidence": "narrates computed facts; does not decide acceptance",
        },
    ]


def _metadata_source_label() -> str:
    if RUN_REGISTRY_FIRESTORE_COLLECTION:
        database = RUN_REGISTRY_FIRESTORE_DATABASE or "(default)"
        project = RUN_REGISTRY_FIRESTORE_PROJECT or "ambient project"
        return f"Firestore metadata: {project}/{database}/{RUN_REGISTRY_FIRESTORE_COLLECTION}"
    if RUN_REGISTRY_URI:
        return f"GCS registry JSON: {RUN_REGISTRY_URI}"
    return "Packaged local registry"


def build_demo_html(*, service_title: str = "BARRED-Fleet") -> str:
    title = html.escape(service_title)
    prompt = html.escape(DEMO_PROMPT)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} Demo</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #080b12;
      --panel: #101725;
      --muted: #8ea0b8;
      --text: #edf4ff;
      --accent: #6ee7b7;
      --warn: #fbbf24;
      --line: #223047;
    }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, #172554 0, var(--bg) 42%);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 48px 20px; }}
    header {{ display: grid; gap: 18px; margin-bottom: 28px; }}
    h1 {{ font-size: clamp(34px, 6vw, 70px); line-height: .92; margin: 0; letter-spacing: -0.06em; }}
    p {{ color: var(--muted); font-size: 16px; line-height: 1.6; max-width: 780px; }}
    button {{
      width: fit-content; border: 0; border-radius: 999px; padding: 12px 18px;
      color: #04130d; background: var(--accent); font-weight: 800; cursor: pointer;
    }}
    button.secondary {{ background: transparent; color: var(--accent); border: 1px solid var(--accent); }}
    button:disabled {{ cursor: not-allowed; opacity: .48; }}
    button.loading::before {{ content: ""; display: inline-block; width: .8em; height: .8em; margin-right: .55em; border: 2px solid currentColor; border-right-color: transparent; border-radius: 999px; vertical-align: -0.1em; animation: spin .8s linear infinite; }}
    label {{ display: grid; gap: 7px; color: var(--muted); font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }}
    select, input {{
      width: 100%; box-sizing: border-box; border: 1px solid var(--line); border-radius: 12px;
      background: #060912; color: var(--text); padding: 11px 12px; font: inherit;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
    .card {{ background: rgba(16, 23, 37, .84); border: 1px solid var(--line); border-radius: 18px; padding: 18px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }}
    .value {{ font-size: 30px; font-weight: 850; letter-spacing: -0.04em; }}
    .controls {{ display: grid; grid-template-columns: minmax(160px, 1fr) minmax(120px, .7fr) auto; gap: 12px; align-items: end; margin-top: 18px; max-width: 720px; }}
    .wide {{ grid-column: span 2; }}
    .full {{ grid-column: 1 / -1; }}
    code, pre, .table {{ background: #060912; border: 1px solid var(--line); border-radius: 12px; }}
    code {{ padding: 2px 6px; }}
    pre {{ overflow: auto; padding: 16px; color: #c7d2fe; }}
    .table {{ overflow: hidden; }}
    .row {{ display: grid; grid-template-columns: 1fr auto; gap: 16px; padding: 12px 14px; border-top: 1px solid var(--line); }}
    .row:first-child {{ border-top: 0; }}
    .row span:first-child {{ color: var(--muted); }}
    .row span:last-child {{ color: var(--text); font-weight: 750; text-align: right; }}
    .note {{ color: var(--muted); margin-top: 12px; font-size: 14px; }}
    .ok {{ color: var(--accent); }}
    .warn {{ color: var(--warn); }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    @media (max-width: 850px) {{ .grid, .controls {{ grid-template-columns: 1fr; }} .wide {{ grid-column: auto; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="card">
        <h2>Cloud Demo</h2>
        <h1>Deterministic vulnerability acceptance, without path handholding.</h1>
        <p>
          This read-only surface calls the deployed BARRED-Fleet backend and renders the
          artifact-backed B-gate result for <code>{html.escape(DEMO_RUN_ID)}</code>.
          The demo prompt is: <code>{prompt}</code>
        </p>
        <button id="refresh">Run deterministic report</button>
      </div>
    </header>
    <section class="card full" aria-labelledby="fresh-seed-heading">
      <h2 id="fresh-seed-heading">Fresh Debate Seed Preview</h2>
      <p>
        Pick an allowlisted seed and run a dry-run plan before any live debate. This page does not
        trigger paid live execution; backend flags still gate that path.
      </p>
      <div class="controls">
        <label for="seed-family">Seed source
          <select id="seed-family">
            <option value="fixture:first">fixture:first</option>
            <option value="cve500">cve500:N</option>
          </select>
        </label>
        <label for="seed-index">CVE index
          <input id="seed-index" type="number" min="0" step="1" value="0" inputmode="numeric">
        </label>
        <button id="preview-seed" type="button">Preview seed metadata</button>
        <button id="run-live" class="secondary" type="button" disabled>Run bounded live debate</button>
        <button id="refresh-live" class="secondary" type="button" disabled>Refresh latest run status</button>
      </div>
      <div id="seed-status" class="note" role="status">No seed preview loaded.</div>
      <div id="seed-metadata" class="table">Select a seed and preview metadata.</div>
      <div class="note">Live execution is bounded to one attempt and requires server-side live flags.</div>
      <article class="card full">
        <h2>Packaged Seed Manifest</h2>
        <div id="seed-manifest" class="table">Loading packaged seed manifest...</div>
        <div class="note">Seed selection is allowlisted; arbitrary paths and raw seed text are not exposed.</div>
      </article>
      <article class="card full">
        <h2>Local Safety Policy</h2>
        <div id="safety-policy" class="table">Loading local safety policy...</div>
        <div class="note">This deterministic policy gates the demo before future Model Armor or Agent Gateway layers.</div>
      </article>
      <article class="card full">
        <h2>Live Debate Result</h2>
        <div id="live-result" class="table">Preview a seed before starting a bounded live run.</div>
        <div class="note">Shows run status, accepted/rejected result, B-gate pass/fail, and Artifact promotion when available.</div>
      </article>
      <article class="card full">
        <h2>Live Invariant Scorecard</h2>
        <div id="live-invariant-scorecard" class="table">Run or preview a seed to see artifact-backed invariants when available.</div>
        <div class="note">Per-run deterministic B-gate metrics only; this panel does not call models or decide acceptance.</div>
      </article>
      <article class="card full">
        <h2>Production Safety Controls</h2>
        <div id="safety-controls" class="table">No safety control receipt loaded.</div>
        <div class="note">Model Armor screens content safety; Agent Gateway controls model/tool egress. Neither decides vulnerability acceptance.</div>
      </article>
    </section>
    <section class="grid">
      <article class="card"><h2>B-gate</h2><div id="gate" class="value">...</div></article>
      <article class="card"><h2>Accepted / Total</h2><div id="rows" class="value">...</div></article>
      <article class="card"><h2>Verifier Parse OK</h2><div id="parse" class="value">...</div></article>
      <article class="card"><h2>Verifier Pass</h2><div id="pass" class="value">...</div></article>
      <article class="card full"><h2>Provenance Chain</h2><div id="chain" class="table">Loading...</div><div class="note">The demo path is metadata → artifacts → deterministic gate → agent narration.</div></article>
      <article class="card wide"><h2>Decision Breakdown</h2><div id="decisions" class="table">Loading...</div></article>
      <article class="card wide"><h2>Invariant Scorecard</h2><div id="invariant-scorecard" class="table">Loading...</div></article>
      <article class="card wide"><h2>Asymmetric Debate Routing</h2><div id="routing" class="table">Loading...</div></article>
      <article class="card wide"><h2>Deterministic Eval</h2><div id="eval" class="table">Loading...</div></article>
      <article class="card full"><h2>Artifact Provenance</h2><div id="provenance" class="table">Loading...</div><div class="note">Artifact facts are computed by deterministic tools; the model only narrates the report.</div></article>
    </section>
  </main>
  <script>
    const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[char]));
    const fmt = (value) => value === null || value === undefined ? "n/a" : value;
    const pct = (value) => value === null || value === undefined ? "n/a" : `${{Math.round(value * 100)}}%`;
    const rows = (items) => items.map(([label, value]) => `<div class="row"><span>${{esc(label)}}</span><span>${{esc(fmt(value))}}</span></div>`).join("");
    const invariantValue = (row) => row.format === "percent" ? pct(row.value) : fmt(row.value);
    function renderInvariantScorecard(target, scorecard) {{
      const panel = document.querySelector(target);
      if (!panel) return;
      if (!scorecard?.available) {{
        panel.innerHTML = rows([
          ["Status", "not available"],
          ["Reason", scorecard?.reason || "pending final B-gate artifacts"],
        ]);
        return;
      }}
      panel.innerHTML = rows((scorecard.rows || []).map((row) => [
        row.label || row.key,
        `${{invariantValue(row)}} · ${{row.direction || "context"}} · ${{row.key}}`,
      ]));
    }}
    const TERMINAL_RUN_STATES = ["completed", "blocked", "failed"];
    let lastPlannedSeedId = null;
    let latestRunId = null;
    function setButtonLoading(button, isLoading, text) {{
      if (!button) return;
      if (!button.dataset.defaultText) button.dataset.defaultText = button.textContent;
      button.disabled = isLoading;
      button.classList.toggle("loading", isLoading);
      button.setAttribute("aria-busy", isLoading ? "true" : "false");
      button.textContent = isLoading ? text : button.dataset.defaultText;
    }}
    const selectedSeedId = () => {{
      const family = document.querySelector("#seed-family").value;
      if (family === "fixture:first") return "fixture:first";
      const index = Number.parseInt(document.querySelector("#seed-index").value, 10);
      return Number.isFinite(index) && index >= 0 ? `cve500:${{index}}` : "cve500:";
    }};
    async function requestFreshDebate(dryRun) {{
      const seedId = selectedSeedId();
      const response = await fetch(dryRun ? "/runs/fresh-demo" : "/runs", {{
        method: "POST",
        headers: {{
          "accept": "application/json",
          "content-type": "application/json",
        }},
        body: JSON.stringify({{
          seed_id: seedId,
          run_id: dryRun ? "fresh-demo-ui-preview" : `fresh-demo-ui-live-${{Date.now()}}`,
          dry_run: dryRun,
          async_mode: !dryRun,
          max_attempts: 1,
        }}),
      }});
      if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
      return response.json();
    }}
    async function loadProductRunReport(runId) {{
      if (!runId) return null;
      const response = await fetch(`/runs/${{encodeURIComponent(runId)}}/report`, {{
        headers: {{ "accept": "application/json" }},
      }});
      if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
      return response.json();
    }}
    async function loadSeedManifest() {{
      const response = await fetch("/seeds/manifest", {{ headers: {{ "accept": "application/json" }} }});
      if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
      const data = await response.json();
      const fixture = data.sources?.fixture || {{}};
      const cve500 = data.sources?.cve500 || {{}};
      document.querySelector("#seed-manifest").innerHTML = rows([
        ["fixture:first", `${{fmt(fixture.count)}} packaged seed · ${{fixture.source_file || "n/a"}}`],
        ["cve500:N", `${{fmt(cve500.count)}} packaged seeds · ${{cve500.source_file || "n/a"}}`],
        ["cve500 hash", cve500.sha256],
        ["Policy", data.selection_policy?.allowlisted_only ? "allowlisted only" : "unknown"],
      ]);
      const policy = data.safety_policy || {{}};
      document.querySelector("#safety-policy").innerHTML = rows([
        ["Status", policy.status],
        ["Seed allowlist", (policy.seed_allowlist || []).join(", ")],
        ["Arbitrary paths", policy.arbitrary_seed_paths_allowed === false ? "blocked" : "unknown"],
        ["Raw seed text", policy.raw_seed_text_exposed === false ? "not exposed" : "unknown"],
        ["Run ID pattern", policy.run_id_pattern],
        ["Model route roles", (policy.model_route_roles || []).join(", ")],
        ["Max attempts", `${{policy.max_attempts?.min ?? "?"}}-${{policy.max_attempts?.max ?? "?"}}; live default ${{policy.max_attempts?.live_default_max ?? "?"}}`],
        ["Timeout seconds", `${{policy.timeout_seconds?.min ?? "?"}}-${{policy.timeout_seconds?.max ?? "?"}}`],
        ["Live gates", (policy.live_execution?.requires_env || []).join(" + ")],
      ]);
    }}
    async function refreshLatestRunStatus() {{
      if (!latestRunId) return null;
      const report = await loadProductRunReport(latestRunId);
      renderLiveResult(report);
      const lifecycle = report?.lifecycle || null;
      const liveButton = document.querySelector("#run-live");
      if (TERMINAL_RUN_STATES.includes(lifecycle?.status)) {{
        liveButton.disabled = false;
      }} else {{
        liveButton.disabled = true;
        document.querySelector("#seed-status").textContent = "Still running; refresh status.";
      }}
      return lifecycle;
    }}
    async function pollRunStatus(runId) {{
      let latest = null;
      const maxAttempts = 80;
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {{
        const response = await fetch(`/runs/${{encodeURIComponent(runId)}}`, {{
          headers: {{ "accept": "application/json" }},
        }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        latest = await response.json();
        renderLiveResult(await loadProductRunReport(runId), latest);
        if (TERMINAL_RUN_STATES.includes(latest.status)) return latest;
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }}
      document.querySelector("#seed-status").textContent = `Still running after 120s. Use Refresh latest run status.`;
      return latest;
    }}
    function lifecycleLabel(data, reportData) {{
      const status = data?.status || "unknown";
      const promotion = reportData?.promotion || data?.promotion || {{}};
      const bGate = reportData?.b_gate || {{}};
      if (status === "queued") return "Queued";
      if (status === "running") return "Running debate";
      if (status === "completed" && promotion.status === "promoted") return "Promoted";
      if (status === "completed" && bGate.passed === false) return "Completed: B-gate failed";
      if (status === "completed") return "Completed";
      if (status === "blocked" && data?.required_env) return "Blocked: live disabled";
      if (status === "blocked") return `Blocked: ${{data?.error_category || "attention required"}}`;
      if (status === "failed") return `Failed: ${{data?.error_category || "runtime error"}}`;
      if (status === "planned") return "Planned dry run";
      return status;
    }}
    function renderSeedMetadata(metadata) {{
      document.querySelector("#seed-metadata").innerHTML = rows([
        ["Seed ID", metadata.seed_id],
        ["Source file", metadata.source_file],
        ["Index", metadata.index],
        ["Language", metadata.language],
        ["Original safety", metadata.original_safety],
        ["Predicate hash", metadata.predicate_sha256],
      ]);
    }}
    function renderLiveResult(reportData, lifecycleData = {{}}) {{
      const data = reportData?.lifecycle || lifecycleData || {{}};
      const artifactReport = reportData?.artifact_report || {{}};
      const bGate = reportData?.b_gate || data.fresh_report?.b_gate || data.b_gate || {{}};
      const metrics = bGate.selected_metrics || {{}};
      const promotion = reportData?.promotion || data.fresh_report?.promotion || data.promotion || {{}};
      const artifactSummary = reportData?.artifact_summary || artifactReport.artifact_summary || {{}};
      const attempts = artifactSummary.artifacts?.attempts || {{}};
      const decisions = attempts.decisions || data.fresh_report?.attempts?.decisions || data.attempts?.decisions || {{}};
      const deterministicEval = reportData?.deterministic_eval || {{}};
      document.querySelector("#live-result").innerHTML = rows([
        ["Run status", data.status],
        ["Lifecycle phase", lifecycleLabel(data, reportData)],
        ["Report status", reportData?.status],
        ["Run ID", reportData?.run_id || data.run_id],
        ["Seed ID", reportData?.seed_id || data.execution?.seed_id || data.seed_id || data.seed_metadata?.seed_id || selectedSeedId()],
        ["Duration", data.duration_ms == null ? "n/a" : `${{data.duration_ms}} ms`],
        ["Accepted rows", metrics.accepted_rows ?? decisions.accepted],
        ["Rejected rows", decisions.rejected],
        ["Verifier parse OK", pct(metrics.verifier_parse_ok_rate)],
        ["Verifier pass", pct(metrics.verifier_pass_rate)],
        ["B-gate pass/fail", (bGate.passed ?? data.b_gate_passed) === true ? "PASS" : (bGate.passed ?? data.b_gate_passed) === false ? "FAIL" : "n/a"],
        ["Deterministic eval", deterministicEval.score],
        ["Artifact promotion", promotion.status || data.promotion_status || "disabled_or_unavailable"],
        ["Artifact report", artifactReport.available === true ? "available" : artifactReport.reason || "not_available"],
        ["Safety policy", reportData?.safety_policy?.status || data.safety_policy?.status],
        ["Safety receipt", reportData?.safety_receipt?.status || data.safety_receipt?.status],
        ["Live flags checked", reportData?.safety_receipt?.live_execution_flags_checked ?? data.safety_receipt?.live_execution_flags_checked],
        ["Model Armor", reportData?.model_armor?.status || "not_configured"],
        ["Agent Gateway", reportData?.agent_gateway?.status || "not_configured"],
        ["Message", data.error || promotion.reason || artifactReport.error || data.fresh_report?.status || lifecycleLabel(data, reportData)],
      ]);
      renderInvariantScorecard("#live-invariant-scorecard", bGate.invariant_scorecard);
      renderSafetyControls(reportData, lifecycleData);
    }}
    function renderSafetyControls(reportData, lifecycleData = {{}}) {{
      const data = reportData?.lifecycle || lifecycleData || {{}};
      const modelArmor = reportData?.model_armor || data.model_armor || {{}};
      const gateway = reportData?.agent_gateway || data.agent_gateway || {{}};
      const seedScreening = modelArmor.seed_screening || modelArmor.screening || {{}};
      const gatewayDecision = gateway.egress_decision || {{}};
      const routePolicy = gateway.model_route_policy || {{}};
      const toolPolicy = gateway.tool_egress_policy || {{}};
      document.querySelector("#safety-controls").innerHTML = rows([
        ["Model Armor status", modelArmor.status || "not_configured"],
        ["Model Armor authority", modelArmor.decision_authority || "none"],
        ["Seed screening", seedScreening.checked ? (seedScreening.blocked ? "blocked" : "passed") : "not checked"],
        ["Seed text stored", seedScreening.input_text_stored ?? modelArmor.input_text_stored ?? "n/a"],
        ["Agent Gateway status", gateway.status || "not_configured"],
        ["Gateway authority", gateway.decision_authority || "none"],
        ["Egress decision", gatewayDecision.checked ? (gatewayDecision.blocked ? `blocked: ${{gatewayDecision.reason}}` : "passed") : "not checked"],
        ["Model route policy", routePolicy.checked ? (routePolicy.blocked ? `blocked: ${{(routePolicy.rejected_routes || []).join(", ")}}` : "passed") : "not checked"],
        ["Tool egress policy", toolPolicy.checked ? (toolPolicy.blocked ? `blocked: ${{(toolPolicy.rejected_tools || []).join(", ")}}` : "passed") : "not checked"],
        ["Acceptance authority", "BARRED deterministic B-gate"],
      ]);
    }}
    async function previewSeed() {{
      const seedId = selectedSeedId();
      document.querySelector("#run-live").disabled = true;
      document.querySelector("#seed-status").textContent = `Planning ${{seedId}}...`;
      const data = await requestFreshDebate(true);
      if (data.status !== "planned") {{
        lastPlannedSeedId = null;
        document.querySelector("#seed-status").textContent = `Rejected: ${{data.error || data.status}}`;
        document.querySelector("#seed-metadata").innerHTML = rows([
          ["Seed ID", seedId],
          ["Status", data.status],
          ["Error", data.error],
        ]);
        return;
      }}
      const metadata = data.seed_metadata || {{}};
      lastPlannedSeedId = metadata.seed_id;
      latestRunId = null;
      document.querySelector("#seed-status").textContent = `Planned ${{metadata.seed_id}} without loading live debate.`;
      document.querySelector("#run-live").disabled = false;
      document.querySelector("#refresh-live").disabled = true;
      renderSeedMetadata(metadata);
      renderLiveResult(null, data);
    }}
    async function runLiveDebate() {{
      const seedId = selectedSeedId();
      if (lastPlannedSeedId !== seedId) {{
        document.querySelector("#live-result").innerHTML = rows([
          ["Run status", "blocked"],
          ["Message", "Preview this seed before live execution."],
        ]);
        return;
      }}
      const liveButton = document.querySelector("#run-live");
      const refreshButton = document.querySelector("#refresh-live");
      let keepLiveDisabled = false;
      setButtonLoading(liveButton, true, "Running bounded live debate");
      refreshButton.disabled = true;
      document.querySelector("#live-result").innerHTML = rows([
        ["Run status", "starting"],
        ["Lifecycle phase", "Starting"],
        ["Seed ID", seedId],
      ]);
      try {{
        const data = await requestFreshDebate(false);
        latestRunId = data.run_id || null;
        refreshButton.disabled = !latestRunId;
        renderLiveResult(await loadProductRunReport(data.run_id), data);
        if (data.run_id && data.status === "queued") {{
          const finalStatus = await pollRunStatus(data.run_id);
          if (!TERMINAL_RUN_STATES.includes(finalStatus?.status)) {{
            keepLiveDisabled = true;
            liveButton.disabled = true;
            document.querySelector("#live-result").innerHTML += rows([
              ["Next action", "Still running; refresh status"],
            ]);
          }}
          return;
        }}
      }} finally {{
        setButtonLoading(liveButton, false);
        liveButton.disabled = keepLiveDisabled;
        if (latestRunId) refreshButton.disabled = false;
      }}
    }}
    async function loadReport() {{
      const response = await fetch("/demo/report", {{ headers: {{ "accept": "application/json" }} }});
      if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
      const data = await response.json();
      const calls = data.model_routing.attempt_models?.by_model_calls || {{}};
      const verifierModels = data.model_routing.attempt_models?.verifier_model_counts || {{}};
      const artifactPaths = data.provenance.artifact_paths || {{}};
      const artifactRegistry = data.provenance.artifact_registry || {{}};
      const chain = data.provenance.chain || [];
      const decisions = data.attempts.decisions || {{}};
      document.querySelector("#gate").textContent = data.b_gate.passed ? "PASS" : "FAIL";
      document.querySelector("#gate").className = data.b_gate.passed ? "value ok" : "value warn";
      document.querySelector("#rows").textContent = `${{fmt(data.b_gate.accepted_rows)}} / ${{fmt(data.b_gate.total_rows)}}`;
      document.querySelector("#parse").textContent = pct(data.b_gate.verifier_parse_ok_rate);
      document.querySelector("#pass").textContent = pct(data.b_gate.verifier_pass_rate);
      document.querySelector("#chain").innerHTML = rows(chain.map((item) => [
        item.step,
        `${{item.system}} · ${{item.evidence}}`,
      ]));
      document.querySelector("#decisions").innerHTML = rows([
        ["Accepted rows", decisions.accepted],
        ["Rejected rows", decisions.rejected],
        ["Attempt rows", data.attempts.row_count],
      ]);
      renderInvariantScorecard("#invariant-scorecard", data.b_gate.invariant_scorecard);
      document.querySelector("#routing").innerHTML = rows([
        ["Generator/debater lane", `${{fmt(calls["ollama/gemma4:31b-cloud"])}} calls · ollama/gemma4:31b-cloud`],
        ["Judge lane", `${{fmt(calls["ollama/gpt-oss:120b-cloud"])}} calls · ollama/gpt-oss:120b-cloud`],
        ["Verifier lane", `${{fmt(verifierModels["ollama/gpt-oss:120b-cloud"])}} rows · ollama/gpt-oss:120b-cloud`],
      ]);
      document.querySelector("#eval").innerHTML = rows([
        ["Contract metric", data.deterministic_eval.summary_metrics?.[0]?.metric_name],
        ["Mean score", data.deterministic_eval.score],
        ["Valid cases", data.deterministic_eval.summary_metrics?.[0]?.num_cases_valid],
      ]);
      document.querySelector("#provenance").innerHTML = rows([
        ["Corpus", artifactRegistry.corpus?.path || artifactPaths.input_path],
        ["Attempts", artifactRegistry.attempts?.path || artifactPaths.attempts_path],
        ["Deterministic eval", artifactRegistry.deterministic_eval_result?.path || artifactPaths.deterministic_eval_result_path],
        ["Diagnostic receipt", artifactRegistry.diagnostic_receipt?.path || "n/a"],
        ["Cache claim", "Cassette replay is local replay, not provider cache telemetry"],
      ]);
      renderSafetyControls(data);
    }}
    document.querySelector("#refresh").addEventListener("click", loadReport);
    document.querySelector("#preview-seed").addEventListener("click", () => {{
      previewSeed().catch((error) => {{
        document.querySelector("#seed-status").textContent = "Seed preview failed.";
        document.querySelector("#seed-metadata").textContent = error.stack || String(error);
      }});
    }});
    document.querySelector("#run-live").addEventListener("click", () => {{
      runLiveDebate().catch((error) => {{
        document.querySelector("#live-result").textContent = error.stack || String(error);
      }});
    }});
    document.querySelector("#refresh-live").addEventListener("click", () => {{
      const refreshButton = document.querySelector("#refresh-live");
      setButtonLoading(refreshButton, true, "Refreshing latest run");
      refreshLatestRunStatus().catch((error) => {{
        document.querySelector("#live-result").textContent = error.stack || String(error);
      }}).finally(() => setButtonLoading(refreshButton, false));
    }});
    loadReport().catch((error) => {{
      document.querySelector("#gate").textContent = "ERROR";
      document.querySelector("#gate").className = "value warn";
      document.querySelector("#provenance").textContent = error.stack || String(error);
    }});
    loadSeedManifest().catch((error) => {{
      document.querySelector("#seed-manifest").textContent = error.stack || String(error);
    }});
  </script>
</body>
</html>"""
