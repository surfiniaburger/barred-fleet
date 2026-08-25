from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from os.path import commonpath
from pathlib import Path
from typing import Any

from app.agent_gateway import build_not_configured_agent_gateway_status
from app.fresh_artifacts import (
    PROMOTE_FRESH_RUNS_ENV,
    PROMOTION_BUCKET_ENV,
    RUN_REGISTRY_FIRESTORE_COLLECTION_ENV,
    RUN_REGISTRY_FIRESTORE_DATABASE_ENV,
    RUN_REGISTRY_FIRESTORE_PROJECT_ENV,
    ArtifactUploader,
)
from app.fresh_debate import (
    FreshDebatePlan,
    FreshDebateRequest,
    plan_fresh_debate_run,
    run_fresh_debate_async,
)
from app.invariant_scorecard import build_invariant_scorecard
from app.model_armor import build_not_configured_model_armor_status
from app.tools import build_artifact_registry, build_observability_report

ProductRunRunner = Callable[[FreshDebateRequest], Awaitable[dict[str, Any]]]
RunStatusWriter = Callable[[str, dict[str, Any]], None]
RunStatusReader = Callable[[str], dict[str, Any] | None]
ProductRunScheduler = Callable[[FreshDebateRequest, dict[str, Any]], None]

_LOCAL_RUN_STATUSES: dict[str, dict[str, Any]] = {}


async def create_product_run(
    request: FreshDebateRequest,
    *,
    runner: ProductRunRunner | None = None,
    env: Mapping[str, str] | None = None,
    status_writer: RunStatusWriter | None = None,
    diagnostic_uploader: ArtifactUploader | None = None,
) -> dict[str, Any]:
    environ = os.environ if env is None else env
    write_status = status_writer or write_run_status
    try:
        plan = plan_fresh_debate_run(request, env=environ)
    except ValueError as exc:
        return {
            "status": "attention_required",
            "run_id": request.run_id or None,
            "error": str(exc),
        }

    if plan.dry_run:
        status_payload = _build_start_status(plan, status="planned")
        write_status(plan.run_id, status_payload)
        return _product_response(status_payload)

    running_status = _build_running_status(plan)
    write_status(plan.run_id, running_status)
    try:
        debate_result = await (runner or run_fresh_debate_async)(request)
    except Exception as exc:
        final_status = _with_diagnostic_receipt(
            plan=plan,
            status_payload=_build_failed_status(
                plan,
                error=str(exc),
                started_at=running_status["started_at"],
            ),
            env=environ,
            uploader=diagnostic_uploader,
        )
        write_status(plan.run_id, final_status)
        return _product_response(final_status)

    final_status = _build_final_status(
        plan=plan,
        debate_result=debate_result,
        started_at=running_status["started_at"],
    )
    final_status = _with_diagnostic_receipt(
        plan=plan,
        status_payload=final_status,
        env=environ,
        uploader=diagnostic_uploader,
    )
    write_status(plan.run_id, final_status)
    return _product_response(final_status)


def queue_product_run(
    request: FreshDebateRequest,
    *,
    schedule: ProductRunScheduler,
    env: Mapping[str, str] | None = None,
    status_writer: RunStatusWriter | None = None,
) -> dict[str, Any]:
    environ = os.environ if env is None else env
    write_status = status_writer or write_run_status
    try:
        plan = plan_fresh_debate_run(request, env=environ)
    except ValueError as exc:
        return {
            "status": "attention_required",
            "run_id": request.run_id or None,
            "error": str(exc),
        }

    status_payload = _build_start_status(plan, status="queued")
    write_status(plan.run_id, status_payload)
    schedule(
        request,
        {
            "env": dict(environ),
            "status_writer": status_writer,
        },
    )
    return _product_response(status_payload)


async def run_queued_product_run(
    request: FreshDebateRequest,
    *,
    runner: ProductRunRunner | None = None,
    env: Mapping[str, str] | None = None,
    status_writer: RunStatusWriter | None = None,
    diagnostic_uploader: ArtifactUploader | None = None,
) -> None:
    environ = os.environ if env is None else env
    write_status = status_writer or write_run_status
    plan = plan_fresh_debate_run(request, env=environ)
    running_status = _build_running_status(plan, preserve_created_at=True)
    write_status(plan.run_id, running_status)
    try:
        debate_result = await (runner or run_fresh_debate_async)(request)
    except Exception as exc:
        write_status(
            plan.run_id,
            _with_diagnostic_receipt(
                plan=plan,
                status_payload=_build_failed_status(
                    plan,
                    error=str(exc),
                    started_at=running_status["started_at"],
                ),
                env=environ,
                uploader=diagnostic_uploader,
            ),
        )
        return

    write_status(
        plan.run_id,
        _with_diagnostic_receipt(
            plan=plan,
            status_payload=_build_final_status(
                plan=plan,
                debate_result=debate_result,
                started_at=running_status["started_at"],
            ),
            env=environ,
            uploader=diagnostic_uploader,
        ),
    )


def get_product_run(
    run_id: str,
    *,
    status_reader: RunStatusReader | None = None,
) -> dict[str, Any]:
    read_status = status_reader or read_run_status
    payload = read_status(run_id)
    if payload is None:
        return {"status": "not_found", "run_id": run_id}
    return payload


def build_product_run_report(
    run_id: str,
    *,
    status_reader: RunStatusReader | None = None,
) -> dict[str, Any]:
    lifecycle = get_product_run(run_id, status_reader=status_reader)
    if lifecycle.get("status") == "not_found":
        return lifecycle

    artifact_paths = _product_artifact_paths(lifecycle)
    diagnostic_receipt_path = str(lifecycle.get("diagnostic_receipt_path") or "")
    deterministic_eval_path = str(
        artifact_paths.get("deterministic_eval_result_path") or ""
    )
    artifact_report = _build_product_artifact_report(
        run_id=str(lifecycle.get("run_id") or run_id),
        artifact_paths=artifact_paths,
        lifecycle_status=str(lifecycle.get("status") or ""),
    )
    artifact_registry = _product_artifact_registry(
        lifecycle=lifecycle,
        artifact_paths=artifact_paths,
        diagnostic_receipt_path=diagnostic_receipt_path,
    )
    b_gate = _product_b_gate_summary(lifecycle, artifact_report=artifact_report)
    deterministic_eval = _product_deterministic_eval_summary(
        deterministic_eval_path,
        artifact_report=artifact_report,
    )

    return {
        "status": "ok",
        "run_id": lifecycle.get("run_id") or run_id,
        "lifecycle": lifecycle,
        "seed_id": lifecycle.get("seed_id"),
        "seed_metadata": lifecycle.get("seed_metadata") or {},
        "model_routes": lifecycle.get("model_routes") or {},
        "safety_policy": lifecycle.get("safety_policy") or {},
        "safety_receipt": lifecycle.get("safety_receipt") or {},
        "model_armor": lifecycle.get("model_armor")
        or build_not_configured_model_armor_status(),
        "agent_gateway": lifecycle.get("agent_gateway")
        or build_not_configured_agent_gateway_status(),
        "max_attempts": lifecycle.get("max_attempts"),
        "artifacts": {
            "paths": artifact_paths,
            "registry": artifact_registry,
            "diagnostic_receipt_path": diagnostic_receipt_path,
        },
        "artifact_registry": artifact_registry,
        "diagnostic": {
            "available": bool(diagnostic_receipt_path),
            "path": diagnostic_receipt_path,
            "error": lifecycle.get("diagnostic_receipt_error", ""),
        },
        "artifact_report": artifact_report,
        "artifact_summary": artifact_report.get("artifact_summary", {}),
        "b_gate": b_gate,
        "deterministic_eval": deterministic_eval,
        "promotion": {
            "status": lifecycle.get("promotion_status") or "not_started",
            "reason": lifecycle.get("promotion_reason") or "",
        },
        "error": lifecycle.get("error"),
        "provenance": {
            "chain": _build_product_report_chain(
                lifecycle=lifecycle,
                diagnostic_receipt_path=diagnostic_receipt_path,
                deterministic_eval_path=deterministic_eval_path,
            )
        },
    }


def write_run_status(run_id: str, payload: dict[str, Any]) -> None:
    collection = os.getenv(RUN_REGISTRY_FIRESTORE_COLLECTION_ENV, "")
    if collection:
        _write_firestore_run_status(run_id, payload)
        return

    existing = _LOCAL_RUN_STATUSES.get(run_id, {})
    _LOCAL_RUN_STATUSES[run_id] = {**existing, **payload}


def read_run_status(run_id: str) -> dict[str, Any] | None:
    collection = os.getenv(RUN_REGISTRY_FIRESTORE_COLLECTION_ENV, "")
    if collection:
        return _read_firestore_run_status(run_id)
    payload = _LOCAL_RUN_STATUSES.get(run_id)
    return dict(payload) if payload is not None else None


def _build_start_status(plan: FreshDebatePlan, *, status: str) -> dict[str, Any]:
    now = _utc_now()
    payload = {
        "run_id": plan.run_id,
        "status": status,
        "seed_id": plan.seed_id,
        "seed_metadata": plan.seed_metadata,
        "model_routes": plan.model_routes,
        "safety_policy": plan.safety_policy,
        "safety_receipt": plan.safety_receipt,
        "model_armor": build_not_configured_model_armor_status(),
        "agent_gateway": build_not_configured_agent_gateway_status(),
        "max_attempts": plan.max_attempts,
        "created_at": now,
        "updated_at": now,
        "b_gate_passed": None,
        "promotion_status": "not_started",
        "promotion_reason": "",
        "artifact_paths": plan.artifact_paths,
        "duration_ms": None,
        "error_category": "",
        "error": None,
    }
    if status == "queued":
        payload["queued_at"] = now
    if status == "running":
        payload["started_at"] = now
    return payload


def _build_running_status(
    plan: FreshDebatePlan,
    *,
    preserve_created_at: bool = False,
) -> dict[str, Any]:
    payload = _build_start_status(plan, status="running")
    if preserve_created_at:
        payload.pop("created_at", None)
    return payload


def _build_final_status(
    *,
    plan: FreshDebatePlan,
    debate_result: dict[str, Any],
    started_at: str,
) -> dict[str, Any]:
    if debate_result.get("status") == "attention_required":
        return _build_blocked_status(
            plan,
            debate_result=debate_result,
            started_at=started_at,
        )
    if debate_result.get("status") == "failed":
        return _build_failed_status(
            plan,
            error=str(debate_result.get("error") or "failed"),
            started_at=started_at,
        )

    fresh_report = _fresh_report(debate_result)
    b_gate = fresh_report.get("b_gate") or {}
    promotion = fresh_report.get("promotion") or {}
    completed_at = _utc_now()
    payload = {
        **_build_start_status(plan, status="completed"),
        "updated_at": completed_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": _duration_ms(started_at, completed_at),
        "b_gate_passed": b_gate.get("passed"),
        "promotion_status": promotion.get("status", "not_promoted"),
        "promotion_reason": promotion.get("reason", ""),
        "artifact_paths": _artifact_paths(debate_result),
        "model_armor": debate_result.get("model_armor")
        or build_not_configured_model_armor_status(),
        "agent_gateway": debate_result.get("agent_gateway")
        or build_not_configured_agent_gateway_status(),
        "error": None,
        "raw_status": debate_result.get("status"),
    }
    payload.pop("created_at", None)
    return payload


def _build_blocked_status(
    plan: FreshDebatePlan,
    *,
    debate_result: dict[str, Any],
    started_at: str | None = None,
) -> dict[str, Any]:
    completed_at = _utc_now()
    payload = {
        **_build_start_status(plan, status="blocked"),
        "updated_at": completed_at,
        "completed_at": completed_at,
        "duration_ms": _duration_ms(started_at, completed_at),
        "error_category": _blocked_error_category(debate_result),
        "error": str(debate_result.get("error") or "attention required"),
        "model_armor": debate_result.get("model_armor")
        or build_not_configured_model_armor_status(),
        "agent_gateway": debate_result.get("agent_gateway")
        or build_not_configured_agent_gateway_status(),
        "required_env": debate_result.get("required_env", ""),
        "artifact_paths": _artifact_paths(debate_result) or plan.artifact_paths,
    }
    if started_at:
        payload["started_at"] = started_at
    payload.pop("created_at", None)
    return payload


def _build_failed_status(
    plan: FreshDebatePlan,
    *,
    error: str,
    started_at: str | None = None,
) -> dict[str, Any]:
    completed_at = _utc_now()
    payload = {
        **_build_start_status(plan, status="failed"),
        "updated_at": completed_at,
        "completed_at": completed_at,
        "duration_ms": _duration_ms(started_at, completed_at),
        "error_category": "runtime_error",
        "error": error,
    }
    if started_at:
        payload["started_at"] = started_at
    payload.pop("created_at", None)
    return payload


def _product_response(status_payload: dict[str, Any]) -> dict[str, Any]:
    promotion_status = status_payload.get("promotion_status") or "not_started"
    response = {
        "status": status_payload.get("status"),
        "run_id": status_payload.get("run_id"),
        "seed_id": status_payload.get("seed_id"),
        "run_status_uri": f"/runs/{status_payload.get('run_id')}",
        "seed_metadata": status_payload.get("seed_metadata") or {},
        "model_routes": status_payload.get("model_routes") or {},
        "safety_policy": status_payload.get("safety_policy") or {},
        "safety_receipt": status_payload.get("safety_receipt") or {},
        "model_armor": status_payload.get("model_armor")
        or build_not_configured_model_armor_status(),
        "agent_gateway": status_payload.get("agent_gateway")
        or build_not_configured_agent_gateway_status(),
        "max_attempts": status_payload.get("max_attempts"),
        "created_at": status_payload.get("created_at"),
        "queued_at": status_payload.get("queued_at"),
        "started_at": status_payload.get("started_at"),
        "completed_at": status_payload.get("completed_at"),
        "updated_at": status_payload.get("updated_at"),
        "duration_ms": status_payload.get("duration_ms"),
        "error_category": status_payload.get("error_category", ""),
        "b_gate_passed": status_payload.get("b_gate_passed"),
        "promotion": {
            "status": promotion_status,
            "reason": status_payload.get("promotion_reason") or "",
        },
        "artifact_paths": status_payload.get("artifact_paths") or {},
        "diagnostic_receipt_path": status_payload.get("diagnostic_receipt_path", ""),
        "diagnostic_receipt_error": status_payload.get("diagnostic_receipt_error", ""),
        "error": status_payload.get("error"),
    }
    if status_payload.get("required_env"):
        response["required_env"] = status_payload["required_env"]
    return response


def _build_product_artifact_report(
    *,
    run_id: str,
    artifact_paths: dict[str, Any],
    lifecycle_status: str = "",
) -> dict[str, Any]:
    if lifecycle_status in {"planned", "queued", "running"}:
        return {
            "available": False,
            "reason": f"{lifecycle_status}_run_has_no_final_artifacts",
            "status": lifecycle_status,
            "artifact_summary": {
                "status": "not_started",
                "artifact_count": 0,
                "artifacts": {},
            },
            "b_gate": {
                "status": "not_evaluated",
                "passed": None,
                "failed_checks": [],
                "selected_metrics": {},
            },
            "eval_results": {
                "llm": None,
                "deterministic": {
                    "path": str(
                        artifact_paths.get("deterministic_eval_result_path") or ""
                    ),
                    "exists": False,
                    "summary_metrics": [],
                },
            },
            "report_checks": {
                "artifacts_read": False,
                "b_gate_passed": False,
                "verifier_parse_ok_rate_met": None,
                "deterministic_eval_present": False,
            },
        }

    input_path = str(artifact_paths.get("input_path") or "")
    if not input_path:
        return {"available": False, "reason": "input_path_missing"}

    attempts_path = str(artifact_paths.get("attempts_path") or "")
    deterministic_eval_result_path = str(
        artifact_paths.get("deterministic_eval_result_path") or ""
    )
    try:
        report = build_observability_report(
            run_id=run_id,
            input_path=input_path,
            attempts_path=attempts_path,
            deterministic_eval_result_path=deterministic_eval_result_path,
            base_dir=_artifact_base_dir(
                input_path,
                attempts_path,
                deterministic_eval_result_path,
            ),
        )
    except Exception as exc:
        return {
            "available": False,
            "reason": "artifact_read_failed",
            "error": str(exc),
        }

    return {
        "available": True,
        "status": report.get("status"),
        "artifact_summary": report.get("artifact_summary", {}),
        "b_gate": report.get("b_gate", {}),
        "eval_results": report.get("eval_results", {}),
        "report_checks": report.get("report_checks", {}),
    }


def _product_artifact_paths(lifecycle: dict[str, Any]) -> dict[str, Any]:
    paths = dict(lifecycle.get("artifact_paths") or {})
    for key in (
        "input_path",
        "attempts_path",
        "checkpoint_path",
        "record_path",
        "cassette_path",
        "llm_eval_result_path",
        "deterministic_eval_result_path",
    ):
        promoted_path = str(lifecycle.get(key) or "")
        current_path = str(paths.get(key) or "")
        if promoted_path and (
            promoted_path.startswith("gs://") or not current_path.startswith("gs://")
        ):
            paths[key] = promoted_path
    return paths


def _product_artifact_registry(
    *,
    lifecycle: dict[str, Any],
    artifact_paths: dict[str, Any],
    diagnostic_receipt_path: str,
) -> dict[str, dict[str, Any]]:
    registry = build_artifact_registry(
        artifact_paths,
        diagnostic_receipt_path=diagnostic_receipt_path,
    )
    if lifecycle.get("status") not in {"planned", "queued", "running"}:
        return registry

    return {
        artifact_kind: {
            **entry,
            "available": False,
            "storage": "not_started" if entry.get("path") else entry.get("storage"),
        }
        for artifact_kind, entry in registry.items()
    }


def _product_b_gate_summary(
    lifecycle: dict[str, Any],
    *,
    artifact_report: dict[str, Any],
) -> dict[str, Any]:
    artifact_b_gate = (
        artifact_report.get("b_gate") if artifact_report.get("available") else None
    )
    if isinstance(artifact_b_gate, dict) and artifact_b_gate.get("status") == "ok":
        selected_metrics = artifact_b_gate.get("selected_metrics", {})
        return {
            "available": True,
            "passed": artifact_b_gate.get("passed"),
            "failed_checks": artifact_b_gate.get("failed_checks", []),
            "selected_metrics": selected_metrics,
            "invariant_scorecard": build_invariant_scorecard(selected_metrics),
        }

    b_gate_available = lifecycle.get("b_gate_passed") is not None
    selected_metrics: dict[str, Any] = {}
    return {
        "available": b_gate_available,
        "passed": lifecycle.get("b_gate_passed") if b_gate_available else None,
        "selected_metrics": selected_metrics,
        "invariant_scorecard": build_invariant_scorecard(selected_metrics),
    }


def _product_deterministic_eval_summary(
    deterministic_eval_path: str,
    *,
    artifact_report: dict[str, Any],
) -> dict[str, Any]:
    deterministic_eval = (
        artifact_report.get("eval_results", {}).get("deterministic")
        if artifact_report.get("available")
        else None
    )
    if isinstance(deterministic_eval, dict):
        return {
            "available": bool(deterministic_eval.get("exists")),
            "path": deterministic_eval_path,
            "summary_metrics": deterministic_eval.get("summary_metrics", []),
            "score": _deterministic_eval_score(deterministic_eval),
        }
    if str(artifact_report.get("reason") or "").endswith("_run_has_no_final_artifacts"):
        return {
            "available": False,
            "path": deterministic_eval_path,
            "summary_metrics": [],
            "score": None,
        }
    return {
        "available": bool(deterministic_eval_path),
        "path": deterministic_eval_path,
    }


def _deterministic_eval_score(deterministic_eval: dict[str, Any]) -> float | None:
    summary_metrics = deterministic_eval.get("summary_metrics") or []
    if not summary_metrics or not isinstance(summary_metrics[0], dict):
        return None
    score = summary_metrics[0].get("mean_score")
    return float(score) if isinstance(score, int | float) else None


def _artifact_base_dir(*path_texts: str) -> Path:
    local_paths = [
        Path(path_text).resolve()
        for path_text in path_texts
        if path_text
        and not path_text.startswith("gs://")
        and Path(path_text).is_absolute()
    ]
    if not local_paths:
        from app.tools import BARRED_ROOT

        return BARRED_ROOT
    if len(local_paths) == 1:
        return local_paths[0].parent
    return Path(commonpath([str(path) for path in local_paths]))


def _fresh_report(debate_result: dict[str, Any]) -> dict[str, Any]:
    report = debate_result.get("fresh_report")
    return report if isinstance(report, dict) else {}


def _artifact_paths(debate_result: dict[str, Any]) -> dict[str, str]:
    fresh_report = _fresh_report(debate_result)
    report_paths = fresh_report.get("artifact_paths")
    if isinstance(report_paths, dict) and report_paths:
        return {str(key): str(value) for key, value in report_paths.items()}

    paths = debate_result.get("artifact_paths")
    if isinstance(paths, dict):
        return {str(key): str(value) for key, value in paths.items()}
    return {}


def _write_firestore_run_status(run_id: str, payload: dict[str, Any]) -> None:
    from google.cloud import firestore

    client = firestore.Client(
        project=os.getenv(RUN_REGISTRY_FIRESTORE_PROJECT_ENV) or None,
        database=os.getenv(RUN_REGISTRY_FIRESTORE_DATABASE_ENV) or None,
    )
    collection = os.getenv(RUN_REGISTRY_FIRESTORE_COLLECTION_ENV, "")
    client.collection(collection).document(run_id).set(
        _drop_none_values(payload),
        merge=True,
    )


def _read_firestore_run_status(run_id: str) -> dict[str, Any] | None:
    from google.cloud import firestore

    client = firestore.Client(
        project=os.getenv(RUN_REGISTRY_FIRESTORE_PROJECT_ENV) or None,
        database=os.getenv(RUN_REGISTRY_FIRESTORE_DATABASE_ENV) or None,
    )
    collection = os.getenv(RUN_REGISTRY_FIRESTORE_COLLECTION_ENV, "")
    snapshot = client.collection(collection).document(run_id).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def _with_diagnostic_receipt(
    *,
    plan: FreshDebatePlan,
    status_payload: dict[str, Any],
    env: Mapping[str, str],
    uploader: ArtifactUploader | None,
) -> dict[str, Any]:
    if status_payload.get("status") not in {"blocked", "failed"}:
        return status_payload

    receipt_path = _write_diagnostic_receipt(plan=plan, status_payload=status_payload)
    diagnostic_error = ""
    try:
        promoted_path = _promote_diagnostic_receipt_if_enabled(
            run_id=plan.run_id,
            receipt_path=receipt_path,
            env=env,
            uploader=uploader,
        )
    except Exception as exc:
        promoted_path = ""
        diagnostic_error = str(exc)
    return {
        **status_payload,
        "diagnostic_receipt_path": promoted_path or str(receipt_path),
        "diagnostic_receipt_error": diagnostic_error,
    }


def _write_diagnostic_receipt(
    *,
    plan: FreshDebatePlan,
    status_payload: dict[str, Any],
) -> Path:
    run_dir = Path(plan.artifact_paths["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = run_dir / "diagnostic_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "run_id": plan.run_id,
                "status": status_payload.get("status"),
                "seed_id": plan.seed_id,
                "seed_metadata": plan.seed_metadata,
                "model_routes": plan.model_routes,
                "safety_policy": plan.safety_policy,
                "safety_receipt": plan.safety_receipt,
                "model_armor": status_payload.get("model_armor")
                or build_not_configured_model_armor_status(),
                "agent_gateway": status_payload.get("agent_gateway")
                or build_not_configured_agent_gateway_status(),
                "max_attempts": plan.max_attempts,
                "error": status_payload.get("error"),
                "error_category": status_payload.get("error_category", ""),
                "required_env": status_payload.get("required_env", ""),
                "created_at": status_payload.get("created_at"),
                "started_at": status_payload.get("started_at"),
                "completed_at": status_payload.get("completed_at"),
                "duration_ms": status_payload.get("duration_ms"),
                "updated_at": status_payload.get("updated_at"),
                "receipt_created_at": _utc_now(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt_path


def _promote_diagnostic_receipt_if_enabled(
    *,
    run_id: str,
    receipt_path: Path,
    env: Mapping[str, str],
    uploader: ArtifactUploader | None,
) -> str:
    if not _env_flag(PROMOTE_FRESH_RUNS_ENV, environ=env):
        return ""
    bucket_uri = env.get(PROMOTION_BUCKET_ENV, "").rstrip("/")
    if not bucket_uri:
        return ""

    target_uri = f"{bucket_uri}/runs/{run_id}/{receipt_path.name}"
    upload = uploader or _upload_gcs_artifact
    upload(receipt_path, target_uri)
    return target_uri


def _upload_gcs_artifact(source_path: Path, target_uri: str) -> None:
    import gcsfs

    filesystem = gcsfs.GCSFileSystem()
    with filesystem.open(target_uri, "wb") as target_file:
        target_file.write(source_path.read_bytes())


def _build_product_report_chain(
    *,
    lifecycle: dict[str, Any],
    diagnostic_receipt_path: str,
    deterministic_eval_path: str,
) -> list[dict[str, str]]:
    chain = [
        {
            "step": "1. Run lifecycle",
            "system": _run_status_source_label(),
            "evidence": str(lifecycle.get("status") or "unknown"),
        }
    ]
    artifact_paths = lifecycle.get("artifact_paths") or {}
    if artifact_paths:
        chain.append(
            {
                "step": "2. Artifact storage",
                "system": _artifact_source_label(artifact_paths),
                "evidence": str(artifact_paths.get("input_path") or "registered"),
            }
        )
    if diagnostic_receipt_path:
        chain.append(
            {
                "step": "3. Diagnostic receipt",
                "system": _path_source_label(diagnostic_receipt_path),
                "evidence": diagnostic_receipt_path,
            }
        )
    if lifecycle.get("b_gate_passed") is not None:
        chain.append(
            {
                "step": "4. Deterministic gate",
                "system": "BARRED offline B-gate",
                "evidence": "pass" if lifecycle.get("b_gate_passed") else "fail",
            }
        )
    else:
        chain.append(
            {
                "step": "4. Deterministic gate",
                "system": "BARRED offline B-gate",
                "evidence": "not evaluated for this lifecycle state",
            }
        )
    if deterministic_eval_path:
        chain.append(
            {
                "step": "5. Deterministic eval receipt",
                "system": _path_source_label(deterministic_eval_path),
                "evidence": deterministic_eval_path,
            }
        )
    return chain


def _run_status_source_label() -> str:
    collection = os.getenv(RUN_REGISTRY_FIRESTORE_COLLECTION_ENV, "")
    if not collection:
        return "Cloud Run local status registry"
    project = os.getenv(RUN_REGISTRY_FIRESTORE_PROJECT_ENV) or "ambient project"
    database = os.getenv(RUN_REGISTRY_FIRESTORE_DATABASE_ENV) or "(default)"
    return f"Firestore metadata: {project}/{database}/{collection}"


def _artifact_source_label(artifact_paths: dict[str, Any]) -> str:
    if any(str(path).startswith("gs://") for path in artifact_paths.values()):
        return "Private GCS artifacts"
    return "Cloud Run local artifacts"


def _path_source_label(path: str) -> str:
    return "Private GCS artifacts" if path.startswith("gs://") else "Cloud Run local artifacts"


def _env_flag(
    name: str,
    *,
    environ: Mapping[str, str],
    default: bool = False,
) -> bool:
    value = environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _drop_none_values(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _duration_ms(started_at: str | None, completed_at: str) -> int | None:
    if not started_at:
        return None
    try:
        started = _parse_utc_timestamp(started_at)
        completed = _parse_utc_timestamp(completed_at)
    except ValueError:
        return None
    return max(0, int((completed - started).total_seconds() * 1000))


def _parse_utc_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _blocked_error_category(debate_result: dict[str, Any]) -> str:
    if debate_result.get("error_category"):
        return str(debate_result["error_category"])
    if debate_result.get("required_env"):
        return "configuration"
    error = str(debate_result.get("error") or "").lower()
    if "b_gate" in error or "b-gate" in error:
        return "b_gate"
    if "seed" in error:
        return "seed"
    return "attention_required"
