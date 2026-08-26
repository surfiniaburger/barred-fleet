from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY = "gepa_empirical_summary"
MEMORY_SOURCE_LOCAL = "local"
MEMORY_SOURCE_GCS = "gcs"
DEFAULT_PARETO_FRONTIER_PATH = Path("../artifacts/gepa/pareto_frontier.json")
DEFAULT_MUTATIONS_PATH = Path("../artifacts/gepa/mutations.jsonl")
DEFAULT_TRACES_PATH = Path("../artifacts/gepa/traces.jsonl")
DEFAULT_ACCEPTANCE_REPORT_PATH = Path("../artifacts/metrics/step4_acceptance_report.json")
GEPA_MEMORY_SOURCE_ENV = "BARRED_GEPA_MEMORY_SOURCE"
GEPA_MEMORY_GCS_URI_ENV = "BARRED_GEPA_MEMORY_GCS_URI"

RAW_TEXT_KEYS = frozenset(
    {
        "code",
        "code_text",
        "model_response",
        "predicate_family",
        "prompt",
        "prompt_text",
        "raw_code",
        "raw_prompt",
        "raw_seed",
        "rationale",
        "response_excerpt",
        "seed_text",
    }
)


class GepaMemoryError(ValueError):
    """Raised when GEPA artifacts cannot be compiled into safe memory."""


def build_gepa_memory_preview(
    env: Mapping[str, str] | None = None,
    *,
    gcs_reader: Any | None = None,
) -> dict[str, Any]:
    """Build a read-only GEPA memory preview from configured local artifact paths."""
    env_map = env or {}
    source = _memory_source(env_map)
    if source == MEMORY_SOURCE_GCS:
        return _build_gcs_memory_preview(env_map, gcs_reader=gcs_reader)
    if source != MEMORY_SOURCE_LOCAL:
        return {
            "status": "attention_required",
            "source": source,
            "error": (
                f"{GEPA_MEMORY_SOURCE_ENV} must be either "
                f"{MEMORY_SOURCE_LOCAL!r} or {MEMORY_SOURCE_GCS!r}"
            ),
            "memory": None,
            "artifact_paths": {},
            "write_enabled": False,
        }

    paths = _configured_artifact_paths(env_map)
    try:
        memory = compile_gepa_memory_from_artifacts(
            pareto_frontier_path=paths["pareto_frontier_path"],
            mutations_path=paths["mutations_path"],
            traces_path=paths["traces_path"],
            acceptance_report_path=paths["acceptance_report_path"],
        )
    except GepaMemoryError as exc:
        return {
            "status": "attention_required",
            "source": MEMORY_SOURCE_LOCAL,
            "error": str(exc),
            "memory": None,
            "artifact_paths": {key: str(value) for key, value in paths.items()},
            "write_enabled": False,
        }

    return {
        "status": "ok",
        "source": MEMORY_SOURCE_LOCAL,
        "memory": memory,
        "artifact_paths": {key: str(value) for key, value in paths.items()},
        "write_enabled": False,
    }


def compile_gepa_memory_from_artifacts(
    *,
    pareto_frontier_path: Path,
    mutations_path: Path | None = None,
    traces_path: Path | None = None,
    acceptance_report_path: Path | None = None,
) -> dict[str, Any]:
    """Compile a redacted GEPA memory document from local artifact files."""
    pareto_frontier = _read_required_json(pareto_frontier_path, "pareto frontier")
    mutations = _read_optional_jsonl(mutations_path)
    traces = _read_optional_jsonl(traces_path)
    acceptance_report = _read_optional_json(acceptance_report_path)

    memory = compile_gepa_memory(
        pareto_frontier=pareto_frontier,
        mutations=mutations,
        traces=traces,
        acceptance_report=acceptance_report,
        source_artifacts={
            "pareto_frontier_path": str(pareto_frontier_path),
            "mutations_path": str(mutations_path or ""),
            "traces_path": str(traces_path or ""),
            "acceptance_report_path": str(acceptance_report_path or ""),
        },
    )
    return memory


def _build_gcs_memory_preview(
    env: Mapping[str, str],
    *,
    gcs_reader: Any | None = None,
) -> dict[str, Any]:
    uri = _text(env.get(GEPA_MEMORY_GCS_URI_ENV))
    if not uri:
        return _gcs_attention(f"{GEPA_MEMORY_GCS_URI_ENV} is required")
    if not uri.startswith("gs://"):
        return _gcs_attention(f"{GEPA_MEMORY_GCS_URI_ENV} must use gs://")

    try:
        memory = _read_gcs_memory(uri, reader=gcs_reader)
    except GepaMemoryError as exc:
        return _gcs_attention(str(exc), uri=uri)

    return {
        "status": "ok",
        "source": MEMORY_SOURCE_GCS,
        "memory": memory,
        "artifact_paths": {"gcs_uri": uri},
        "write_enabled": False,
    }


def _gcs_attention(error: str, *, uri: str = "") -> dict[str, Any]:
    artifact_paths = {"gcs_uri": uri} if uri else {}
    return {
        "status": "attention_required",
        "source": MEMORY_SOURCE_GCS,
        "error": error,
        "memory": None,
        "artifact_paths": artifact_paths,
        "write_enabled": False,
    }


def _read_gcs_memory(uri: str, *, reader: Any | None = None) -> Mapping[str, Any]:
    text = reader(uri) if reader is not None else _read_gcs_text(uri)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GepaMemoryError(f"GCS GEPA memory summary is not valid JSON: {uri}") from exc
    if not isinstance(payload, Mapping):
        raise GepaMemoryError(f"GCS GEPA memory summary must be an object: {uri}")

    memory = payload.get("memory", payload)
    if not isinstance(memory, Mapping):
        raise GepaMemoryError(f"GCS GEPA memory payload must contain a memory object: {uri}")
    if _text(memory.get("memory_kind")) != MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY:
        raise GepaMemoryError(
            f"GCS GEPA memory payload must have memory_kind={MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY}"
        )
    _assert_redacted(memory)
    return dict(memory)


def _read_gcs_text(uri: str) -> str:
    import gcsfs

    filesystem = gcsfs.GCSFileSystem()
    with filesystem.open(uri, "r") as memory_file:
        return memory_file.read()


def _memory_source(env: Mapping[str, str]) -> str:
    return _text(env.get(GEPA_MEMORY_SOURCE_ENV)) or MEMORY_SOURCE_LOCAL


def _configured_artifact_paths(env: Mapping[str, str]) -> dict[str, Path]:
    return {
        "pareto_frontier_path": Path(
            env.get("BARRED_GEPA_PARETO_FRONTIER_PATH", "")
            or DEFAULT_PARETO_FRONTIER_PATH
        ),
        "mutations_path": Path(
            env.get("BARRED_GEPA_MUTATIONS_PATH", "") or DEFAULT_MUTATIONS_PATH
        ),
        "traces_path": Path(
            env.get("BARRED_GEPA_TRACES_PATH", "") or DEFAULT_TRACES_PATH
        ),
        "acceptance_report_path": Path(
            env.get("BARRED_GEPA_ACCEPTANCE_REPORT_PATH", "")
            or DEFAULT_ACCEPTANCE_REPORT_PATH
        ),
    }


def compile_gepa_memory(
    *,
    pareto_frontier: Mapping[str, Any],
    mutations: Iterable[Mapping[str, Any]] = (),
    traces: Iterable[Mapping[str, Any]] = (),
    acceptance_report: Mapping[str, Any] | None = None,
    source_artifacts: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compile a Firestore-ready GEPA empirical summary without raw text."""
    if not isinstance(pareto_frontier, Mapping) or not pareto_frontier:
        raise GepaMemoryError("pareto frontier must be a non-empty object")

    pareto_summary = _summarize_pareto_frontier(pareto_frontier)
    mutation_summary = _summarize_mutations(mutations)
    trace_summary = _summarize_traces(traces)
    audit_summary = _summarize_acceptance_audit(acceptance_report or {})

    stable_payload = {
        "acceptance_audit": audit_summary,
        "memory_kind": MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY,
        "mutation_summary": mutation_summary,
        "pareto_frontier": pareto_summary,
        "schema_version": SCHEMA_VERSION,
        "trace_summary": trace_summary,
    }

    memory = {
        "memory_id": _stable_memory_id(stable_payload),
        "created_at": _utc_now_iso(),
        "memory_kind": MEMORY_KIND_GEPA_EMPIRICAL_SUMMARY,
        "source_artifacts": dict(source_artifacts or {}),
        "pareto_frontier": pareto_summary,
        "mutation_summary": mutation_summary,
        "trace_summary": trace_summary,
        "acceptance_audit": audit_summary,
        "decision_authority": "deterministic_b_gate_only",
        "raw_prompt_text_stored": False,
        "raw_seed_text_stored": False,
        "raw_code_text_stored": False,
        "schema_version": SCHEMA_VERSION,
    }
    _assert_redacted(memory)
    return memory


def _summarize_pareto_frontier(frontier: Mapping[str, Any]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    best_bucket = ""
    best_score: float | None = None

    for bucket, raw_entry in sorted(frontier.items()):
        if not isinstance(bucket, str) or not isinstance(raw_entry, Mapping):
            continue
        score = _optional_float(raw_entry.get("score"))
        prompt = _text(raw_entry.get("prompt"))
        entry = {
            "variant_id": _text(raw_entry.get("variant_id")),
            "score": score,
            "updated_at": _text(raw_entry.get("updated_at")),
            "prompt_sha256": _sha256_text(prompt) if prompt else "",
            "raw_prompt_text_stored": False,
        }
        buckets[bucket] = entry
        if score is not None and (best_score is None or score > best_score):
            best_score = score
            best_bucket = bucket

    if not buckets:
        raise GepaMemoryError("pareto frontier has no valid bucket entries")

    return {
        "bucket_count": len(buckets),
        "best_bucket": best_bucket,
        "best_score": best_score,
        "buckets": buckets,
    }


def _summarize_mutations(mutations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [row for row in mutations if isinstance(row, Mapping)]
    taxonomy_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    positive_score_count = 0
    negative_score_count = 0

    for row in rows:
        taxonomy = _text(row.get("taxonomy_bucket"))
        if taxonomy:
            taxonomy_counts[taxonomy] += 1
        rule = _text(row.get("topological_rule"))
        if rule:
            rule_counts[rule] += 1
        score = _optional_float(row.get("score"))
        if score is not None and score > 0:
            positive_score_count += 1
        if score is not None and score < 0:
            negative_score_count += 1

    return {
        "total_mutations": len(rows),
        "by_taxonomy_bucket": dict(sorted(taxonomy_counts.items())),
        "by_topological_rule": dict(sorted(rule_counts.items())),
        "positive_score_count": positive_score_count,
        "negative_score_count": negative_score_count,
    }


def _summarize_traces(traces: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [row for row in traces if isinstance(row, Mapping)]
    outcome_counts: Counter[str] = Counter()
    variant_counts: Counter[str] = Counter()
    run_ids: set[str] = set()

    for row in rows:
        outcome = _text(row.get("outcome"))
        if outcome:
            outcome_counts[outcome] += 1
        mutation_id = _text(row.get("canonical_mutation_id"))
        if mutation_id:
            variant_counts[mutation_id] += 1
        details = row.get("details")
        if isinstance(details, Mapping):
            run_id = _text(details.get("run_id"))
            if run_id:
                run_ids.add(run_id)

    return {
        "total_traces": len(rows),
        "by_outcome": dict(sorted(outcome_counts.items())),
        "by_variant": dict(sorted(variant_counts.items())),
        "run_ids": sorted(run_ids),
    }


def _summarize_acceptance_audit(report: Mapping[str, Any]) -> dict[str, Any]:
    invariants = [
        _summarize_invariant(invariant)
        for invariant in report.get("invariants", [])
        if isinstance(invariant, Mapping)
    ]
    passed_count = sum(1 for invariant in invariants if invariant.get("passed") is True)
    return {
        "status": _text(report.get("status")),
        "all_invariants_passed": _optional_bool(report.get("all_invariants_passed")),
        "passed_invariants": passed_count,
        "total_invariants": len(invariants),
        "dataset_summary": dict(_mapping(report.get("dataset_summary"))),
        "invariants": invariants,
    }


def _summarize_invariant(invariant: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(invariant.get("id")),
        "name": _text(invariant.get("name")),
        "measured": _text(invariant.get("measured")),
        "passed": _optional_bool(invariant.get("passed")),
    }


def _read_required_json(path: Path, label: str) -> Mapping[str, Any]:
    if not path.exists():
        raise GepaMemoryError(f"{label} artifact does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GepaMemoryError(f"{label} artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, Mapping):
        raise GepaMemoryError(f"{label} artifact must contain a JSON object: {path}")
    return payload


def _read_optional_json(path: Path | None) -> Mapping[str, Any]:
    if path is None or not path.exists():
        return {}
    return _read_required_json(path, "optional JSON")


def _read_optional_jsonl(path: Path | None) -> list[Mapping[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[Mapping[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            rows.append(payload)
    return rows


def _stable_memory_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{_sha256_text(serialized)}"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _assert_redacted(memory: Mapping[str, Any]) -> None:
    serialized = json.dumps(memory, sort_keys=True)
    forbidden_keys = RAW_TEXT_KEYS.intersection(memory)
    if forbidden_keys:
        joined = ", ".join(sorted(forbidden_keys))
        raise GepaMemoryError(f"memory contains forbidden raw text keys: {joined}")
    if "RAW " in serialized:
        raise GepaMemoryError("memory contains obvious raw fixture text")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


class ParetoSpecialist:
    """Represents a domain-specialized prompt invariant stored in the Pareto Memory Bank."""

    def __init__(
        self,
        taxonomy_bucket: str,
        prompt: str,
        score: float,
        updated_at: str,
        variant_id: str,
    ) -> None:
        self.taxonomy_bucket = taxonomy_bucket
        self.prompt = prompt
        self.score = score
        self.updated_at = updated_at
        self.variant_id = variant_id
        self.prompt_sha256 = _sha256_text(prompt) if prompt else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "taxonomy_bucket": self.taxonomy_bucket,
            "score": self.score,
            "variant_id": self.variant_id,
            "prompt_sha256": self.prompt_sha256,
            "updated_at": self.updated_at,
        }

    def format_micro_directive(self) -> str:
        """Extract a concise 15-30 token micro-directive from the specialist prompt."""
        lines = [line.strip() for line in self.prompt.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("1.") or line.startswith("-") or "Focus on" in line:
                return line
        return lines[0] if lines else f"Specialize analysis for {self.taxonomy_bucket}."


def load_pareto_specialists(
    pareto_frontier_path: Path | None = None,
) -> dict[str, ParetoSpecialist]:
    """Load active Pareto specialists from the Pareto Memory Bank artifact."""
    target_path = pareto_frontier_path or DEFAULT_PARETO_FRONTIER_PATH
    if not target_path.exists():
        # Fallback to local sibling path if run inside barred-fleet subdirectory
        alt_path = Path("artifacts/gepa/pareto_frontier.json")
        if alt_path.exists():
            target_path = alt_path
        else:
            return {}

    raw_data = _read_optional_json(target_path)
    specialists: dict[str, ParetoSpecialist] = {}
    for bucket, entry in raw_data.items():
        if isinstance(entry, Mapping):
            specialists[bucket] = ParetoSpecialist(
                taxonomy_bucket=bucket,
                prompt=_text(entry.get("prompt")),
                score=_optional_float(entry.get("score")) or 0.0,
                updated_at=_text(entry.get("updated_at")),
                variant_id=_text(entry.get("variant_id")),
            )
    return specialists


def get_pareto_directive_for_taxonomy(
    taxonomy: str,
    pareto_frontier_path: Path | None = None,
) -> str:
    """Retrieve the optimal Pareto micro-directive for a given vulnerability taxonomy."""
    specialists = load_pareto_specialists(pareto_frontier_path)
    if taxonomy in specialists:
        return specialists[taxonomy].format_micro_directive()
    return f"Enforce strict AST reachability invariants for {taxonomy}."

