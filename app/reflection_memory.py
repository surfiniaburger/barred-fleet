from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = 1
MEMORY_KIND_RUN_OUTCOME = "run_outcome_summary"

DIAGNOSTIC_ACCEPTED = "accepted"
DIAGNOSTIC_B_GATE_REJECTED = "b_gate_rejected"
DIAGNOSTIC_CONTENT_SAFETY_BLOCKED = "content_safety_blocked"
DIAGNOSTIC_EGRESS_POLICY_BLOCKED = "egress_policy_blocked"
DIAGNOSTIC_CONFIGURATION_BLOCKED = "configuration_blocked"
DIAGNOSTIC_RUNNER_FAILED = "runner_failed"

RAW_TEXT_KEYS = frozenset(
    {
        "raw_prompt",
        "raw_prompt_text",
        "prompt",
        "prompt_text",
        "raw_seed",
        "raw_seed_text",
        "seed_text",
        "code",
        "code_text",
        "raw_code",
        "raw_code_text",
        "response_excerpt",
        "judge_rationale",
        "model_response",
    }
)


class ReflectionMemoryError(ValueError):
    """Raised when a report cannot be compiled into a memory document."""


def compile_reflection_memory(report: Mapping[str, Any]) -> dict[str, Any]:
    """Compile one redacted memory document from an artifact-backed run report."""
    run_id = _required_text(report, "run_id")
    diagnostic_bucket = classify_reflection_report(report)
    seed_metadata = _mapping(report.get("seed_metadata"))
    b_gate = _mapping(report.get("b_gate"))
    deterministic_eval = _mapping(report.get("deterministic_eval"))
    promotion = _mapping(report.get("promotion"))
    model_armor = _mapping(report.get("model_armor"))
    agent_gateway = _mapping(report.get("agent_gateway"))
    artifact_registry = _mapping(report.get("artifact_registry"))
    selected_metrics = _mapping(b_gate.get("selected_metrics"))

    memory = {
        "memory_id": _memory_id(
            run_id=run_id,
            diagnostic_bucket=diagnostic_bucket,
            seed_id=_text(report.get("seed_id")),
        ),
        "source_run_id": run_id,
        "source_report_uri": _source_report_uri(
            deterministic_eval=deterministic_eval,
            artifact_registry=artifact_registry,
        ),
        "created_at": _utc_now_iso(),
        "memory_kind": MEMORY_KIND_RUN_OUTCOME,
        "predicate_family": _predicate_family(seed_metadata),
        "seed_id": _text(report.get("seed_id")),
        "seed_source": _text(seed_metadata.get("source_file")),
        "seed_index": _seed_index(seed_metadata),
        "b_gate_passed": _optional_bool(b_gate.get("passed")),
        "promotion_status": _text(promotion.get("status")),
        "verifier_parse_ok_rate": _optional_float(
            selected_metrics.get("verifier_parse_ok_rate")
        ),
        "verifier_pass_rate": _optional_float(
            selected_metrics.get("verifier_pass_rate")
        ),
        "model_routes": dict(_mapping(report.get("model_routes"))),
        "safety_controls": _safety_controls(
            model_armor=model_armor,
            agent_gateway=agent_gateway,
        ),
        "diagnostic_bucket": diagnostic_bucket,
        "lesson": _lesson_for(diagnostic_bucket),
        "negative_constraints": _negative_constraints_for(diagnostic_bucket),
        "positive_constraints": _positive_constraints_for(diagnostic_bucket),
        "raw_prompt_text_stored": False,
        "raw_seed_text_stored": False,
        "raw_code_text_stored": False,
        "schema_version": SCHEMA_VERSION,
    }
    _assert_redacted(memory)
    return memory


def classify_reflection_report(report: Mapping[str, Any]) -> str:
    """Classify a product run report into one reflection memory bucket."""
    model_armor = _mapping(report.get("model_armor"))
    seed_screening = _mapping(model_armor.get("seed_screening"))
    if seed_screening.get("blocked") is True:
        return DIAGNOSTIC_CONTENT_SAFETY_BLOCKED

    agent_gateway = _mapping(report.get("agent_gateway"))
    egress_decision = _mapping(agent_gateway.get("egress_decision"))
    if egress_decision.get("blocked") is True:
        return DIAGNOSTIC_EGRESS_POLICY_BLOCKED

    lifecycle = _mapping(report.get("lifecycle"))
    lifecycle_status = _text(lifecycle.get("status") or report.get("status"))
    error_category = _text(lifecycle.get("error_category") or report.get("error_category"))
    if lifecycle_status == "blocked" and error_category == "configuration":
        return DIAGNOSTIC_CONFIGURATION_BLOCKED
    if lifecycle_status == "failed":
        return DIAGNOSTIC_RUNNER_FAILED

    b_gate = _mapping(report.get("b_gate"))
    if b_gate.get("passed") is True:
        return DIAGNOSTIC_ACCEPTED
    if b_gate.get("passed") is False:
        return DIAGNOSTIC_B_GATE_REJECTED
    return DIAGNOSTIC_RUNNER_FAILED


def _required_text(report: Mapping[str, Any], key: str) -> str:
    value = _text(report.get(key))
    if not value:
        raise ReflectionMemoryError(f"report is missing required field: {key}")
    return value


def _memory_id(*, run_id: str, diagnostic_bucket: str, seed_id: str) -> str:
    payload = {
        "diagnostic_bucket": diagnostic_bucket,
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "seed_id": seed_id,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _source_report_uri(
    *,
    deterministic_eval: Mapping[str, Any],
    artifact_registry: Mapping[str, Any],
) -> str:
    deterministic_path = _text(deterministic_eval.get("path"))
    if deterministic_path:
        return deterministic_path
    registry_eval = _mapping(artifact_registry.get("deterministic_eval_result"))
    return _text(registry_eval.get("path"))


def _predicate_family(seed_metadata: Mapping[str, Any]) -> str:
    for key in ("predicate_family", "vulnerability_family", "family"):
        value = _text(seed_metadata.get(key))
        if value:
            return value
    return "unknown"


def _seed_index(seed_metadata: Mapping[str, Any]) -> int | None:
    for key in ("index", "seed_index", "source_index"):
        value = seed_metadata.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _safety_controls(
    *,
    model_armor: Mapping[str, Any],
    agent_gateway: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "model_armor_status": _text(model_armor.get("status")),
        "model_armor_mode": _text(model_armor.get("mode")),
        "agent_gateway_status": _text(agent_gateway.get("status")),
        "agent_gateway_mode": _text(agent_gateway.get("mode")),
        "agent_gateway_blocked": _optional_bool(
            _mapping(agent_gateway.get("egress_decision")).get("blocked")
        ),
    }


def _lesson_for(diagnostic_bucket: str) -> str:
    lessons = {
        DIAGNOSTIC_ACCEPTED: (
            "Accepted by deterministic B-gate with artifact-backed verifier receipts."
        ),
        DIAGNOSTIC_B_GATE_REJECTED: (
            "Generated artifact was rejected by deterministic B-gate; do not promote this pattern."
        ),
        DIAGNOSTIC_CONTENT_SAFETY_BLOCKED: (
            "Model Armor blocked seed or content before live execution."
        ),
        DIAGNOSTIC_EGRESS_POLICY_BLOCKED: (
            "Agent Gateway blocked route or tool egress before live execution."
        ),
        DIAGNOSTIC_CONFIGURATION_BLOCKED: (
            "Run was blocked by configuration before live execution completed."
        ),
        DIAGNOSTIC_RUNNER_FAILED: (
            "Run failed or lacked enough deterministic evidence for memory promotion."
        ),
    }
    return lessons.get(diagnostic_bucket, lessons[DIAGNOSTIC_RUNNER_FAILED])


def _positive_constraints_for(diagnostic_bucket: str) -> list[str]:
    if diagnostic_bucket == DIAGNOSTIC_ACCEPTED:
        return [
            "Preserve exact code anchors.",
            "Keep source and sink claims tied to deterministic artifacts.",
        ]
    return ["Require artifact-backed evidence before promotion."]


def _negative_constraints_for(diagnostic_bucket: str) -> list[str]:
    constraints = {
        DIAGNOSTIC_B_GATE_REJECTED: [
            "Do not promote patterns rejected by deterministic B-gate."
        ],
        DIAGNOSTIC_CONTENT_SAFETY_BLOCKED: [
            "Do not bypass Model Armor seed screening."
        ],
        DIAGNOSTIC_EGRESS_POLICY_BLOCKED: [
            "Do not route through unapproved model or tool egress."
        ],
        DIAGNOSTIC_CONFIGURATION_BLOCKED: [
            "Do not treat configuration refusal as model evidence."
        ],
        DIAGNOSTIC_RUNNER_FAILED: [
            "Do not infer a vulnerability lesson from failed execution."
        ],
    }
    return constraints.get(diagnostic_bucket, [])


def _assert_redacted(memory: Mapping[str, Any]) -> None:
    forbidden = RAW_TEXT_KEYS.intersection(memory)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise ReflectionMemoryError(f"memory contains forbidden raw text keys: {joined}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
