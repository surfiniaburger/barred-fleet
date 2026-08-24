from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.agent_gateway import AgentGateway, build_agent_gateway
from app.debate_stack import (
    RUNTIME_ROOT_ENV,
    DebateStackConfig,
    DebateStackHandle,
    should_start_internal_debate_stack,
    start_internal_debate_stack,
)
from app.model_armor import TextSafetyScreen, build_text_safety_screen

DEFAULT_MODEL_ROUTES = {
    "generator": "vertex_ai/gemini-3.5-flash-lite",
    "judge": "vertex_ai/gemini-3.6-flash",
    "verifier": "vertex_ai/gemini-3.6-flash",
}
ALLOWED_FIXTURE_SEEDS = {"fixture:first"}
CVE500_SEED_PREFIX = "cve500:"
MODEL_ARMOR_BLOCK_SMOKE_SEED_ID = "smoke:model-armor-block"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
TMP_ROOT_ENV = "BARRED_FRESH_DEBATE_TMP_DIR"
SEEDS_PATH_ENV = "BARRED_FRESH_DEBATE_SEEDS_PATH"
MAX_LIVE_ATTEMPTS_ENV = "BARRED_MAX_LIVE_FRESH_ATTEMPTS"
DEFAULT_JUDGE_URL = "http://127.0.0.1:9009"


class FreshDebateRequest(BaseModel):
    seed_id: str
    run_id: str = ""
    dry_run: bool = True
    async_mode: bool = False
    max_attempts: int = 1
    timeout_seconds: int = 180
    judge_url: str = DEFAULT_JUDGE_URL
    model_routes: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class FreshDebatePlan:
    run_id: str
    seed_id: str
    seed_topic: str
    seed_predicate: str
    seed_metadata: dict[str, Any]
    dry_run: bool
    max_attempts: int
    timeout_seconds: int
    judge_url: str
    model_routes: dict[str, str]
    artifact_paths: dict[str, str]
    safety_policy: dict[str, Any]
    safety_receipt: dict[str, Any]


FreshDebateRunner = Callable[[FreshDebatePlan], dict[str, Any]]
AsyncFreshDebateRunner = Callable[[FreshDebatePlan], Any]


def run_fresh_debate(
    request: FreshDebateRequest,
    *,
    runner: FreshDebateRunner | None = None,
    env: Mapping[str, str] | None = None,
    safety_screen: TextSafetyScreen | None = None,
    agent_gateway: AgentGateway | None = None,
) -> dict[str, Any]:
    environ = os.environ if env is None else env
    if not _env_flag("BARRED_ENABLE_FRESH_DEBATE", environ=environ):
        return {
            "status": "attention_required",
            "run_id": None,
            "error": "fresh debate execution is disabled",
            "required_env": "BARRED_ENABLE_FRESH_DEBATE=true",
        }

    try:
        plan = plan_fresh_debate_run(request, env=environ)
    except ValueError as exc:
        return {
            "status": "attention_required",
            "run_id": request.run_id or None,
            "error": str(exc),
        }

    if plan.dry_run:
        return _planned_response(plan)

    model_armor = _screen_seed_for_live_execution(
        plan,
        safety_screen=safety_screen,
        env=environ,
    )
    if _model_armor_blocked(model_armor):
        return _blocked_by_seed_screen_response(plan, model_armor)

    gateway = _evaluate_agent_gateway_for_live_execution(
        plan,
        agent_gateway=agent_gateway,
        env=environ,
    )
    if _agent_gateway_blocked(gateway):
        return _blocked_by_agent_gateway_response(plan, model_armor, gateway)

    if not _env_flag("BARRED_ENABLE_LIVE_FRESH_DEBATE", environ=environ):
        return {
            "status": "attention_required",
            "run_id": plan.run_id,
            "error": "live fresh debate execution is disabled",
            "required_env": "BARRED_ENABLE_LIVE_FRESH_DEBATE=true",
            "model_armor": model_armor,
            "agent_gateway": gateway,
        }
    live_policy_error = _validate_live_policy(plan, env=environ)
    if live_policy_error is not None:
        return {
            **live_policy_error,
            "model_armor": model_armor,
            "agent_gateway": gateway,
        }

    if runner is None:
        return {
            "status": "attention_required",
            "run_id": plan.run_id,
            "error": "fresh debate runner is not implemented",
            "model_armor": model_armor,
            "agent_gateway": gateway,
        }
    try:
        return _attach_safety_controls(runner(plan), model_armor, gateway)
    except Exception as exc:
        return {
            "status": "attention_required",
            "run_id": plan.run_id,
            "error": f"fresh debate runner failed: {exc}",
            "model_armor": model_armor,
            "agent_gateway": gateway,
        }


async def run_fresh_debate_async(
    request: FreshDebateRequest,
    *,
    runner: AsyncFreshDebateRunner | None = None,
    env: Mapping[str, str] | None = None,
    safety_screen: TextSafetyScreen | None = None,
    agent_gateway: AgentGateway | None = None,
) -> dict[str, Any]:
    environ = os.environ if env is None else env
    if not _env_flag("BARRED_ENABLE_FRESH_DEBATE", environ=environ):
        return {
            "status": "attention_required",
            "run_id": None,
            "error": "fresh debate execution is disabled",
            "required_env": "BARRED_ENABLE_FRESH_DEBATE=true",
        }

    try:
        plan = plan_fresh_debate_run(request, env=environ)
    except ValueError as exc:
        return {
            "status": "attention_required",
            "run_id": request.run_id or None,
            "error": str(exc),
        }

    if plan.dry_run:
        return _planned_response(plan)

    model_armor = _screen_seed_for_live_execution(
        plan,
        safety_screen=safety_screen,
        env=environ,
    )
    if _model_armor_blocked(model_armor):
        return _blocked_by_seed_screen_response(plan, model_armor)

    gateway = _evaluate_agent_gateway_for_live_execution(
        plan,
        agent_gateway=agent_gateway,
        env=environ,
    )
    if _agent_gateway_blocked(gateway):
        return _blocked_by_agent_gateway_response(plan, model_armor, gateway)

    if not _env_flag("BARRED_ENABLE_LIVE_FRESH_DEBATE", environ=environ):
        return {
            "status": "attention_required",
            "run_id": plan.run_id,
            "error": "live fresh debate execution is disabled",
            "required_env": "BARRED_ENABLE_LIVE_FRESH_DEBATE=true",
            "model_armor": model_armor,
            "agent_gateway": gateway,
        }
    live_policy_error = _validate_live_policy(plan, env=environ)
    if live_policy_error is not None:
        return {
            **live_policy_error,
            "model_armor": model_armor,
            "agent_gateway": gateway,
        }

    try:
        if runner is None:
            result = await _execute_existing_a2a_debate(
                plan,
                model_armor=model_armor,
                agent_gateway=gateway,
            )
        else:
            result = await runner(plan)
        return _attach_safety_controls(result, model_armor, gateway)
    except Exception as exc:
        return {
            "status": "attention_required",
            "run_id": plan.run_id,
            "error": f"fresh debate runner failed: {exc}",
            "model_armor": model_armor,
            "agent_gateway": gateway,
        }



def _screen_seed_for_live_execution(
    plan: FreshDebatePlan,
    *,
    safety_screen: TextSafetyScreen | None,
    env: Mapping[str, str],
) -> dict[str, Any]:
    screen = safety_screen or build_text_safety_screen(env=env)
    result = screen.screen_text(
        text=f"{plan.seed_topic}\n\nPredicate: {plan.seed_predicate}",
        context="fresh_debate.seed",
    )
    return {
        **result,
        "seed_screening": {
            **(result.get("seed_screening") or {}),
            "kind": "seed",
        },
    }


def _model_armor_blocked(model_armor: dict[str, Any]) -> bool:
    seed_screening = model_armor.get("seed_screening")
    if isinstance(seed_screening, dict) and seed_screening.get("blocked") is True:
        return True
    screening = model_armor.get("screening")
    return isinstance(screening, dict) and screening.get("blocked") is True


def _evaluate_agent_gateway_for_live_execution(
    plan: FreshDebatePlan,
    *,
    agent_gateway: AgentGateway | None,
    env: Mapping[str, str],
) -> dict[str, Any]:
    gateway = agent_gateway or build_agent_gateway(env=env)
    return gateway.evaluate_egress(
        model_routes=plan.model_routes,
        tool_names=["fresh_debate"],
        context="fresh_debate.live_execution",
    )


def _agent_gateway_blocked(gateway: dict[str, Any]) -> bool:
    decision = gateway.get("egress_decision")
    if isinstance(decision, dict) and decision.get("blocked") is True:
        return True
    return gateway.get("status") in {"blocked", "error"}


def _blocked_by_seed_screen_response(
    plan: FreshDebatePlan,
    model_armor: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "attention_required",
        "run_id": plan.run_id,
        "error": "model armor seed screening blocked live execution",
        "error_category": "content_safety",
        "model_armor": model_armor,
    }


def _blocked_by_agent_gateway_response(
    plan: FreshDebatePlan,
    model_armor: dict[str, Any],
    agent_gateway: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "attention_required",
        "run_id": plan.run_id,
        "error": "agent gateway blocked live execution",
        "error_category": "egress_policy",
        "model_armor": model_armor,
        "agent_gateway": agent_gateway,
    }


def _attach_safety_controls(
    result: dict[str, Any],
    model_armor: dict[str, Any],
    agent_gateway: dict[str, Any],
) -> dict[str, Any]:
    return {
        **result,
        "model_armor": result.get("model_armor") or model_armor,
        "agent_gateway": result.get("agent_gateway") or agent_gateway,
    }

def plan_fresh_debate_run(
    request: FreshDebateRequest,
    *,
    env: Mapping[str, str] | None = None,
) -> FreshDebatePlan:
    environ = os.environ if env is None else env
    seed = _resolve_seed(request.seed_id, env=environ)
    _validate_limits(request.max_attempts, request.timeout_seconds)
    run_id = _normalize_or_create_run_id(request.run_id)
    return FreshDebatePlan(
        run_id=run_id,
        seed_id=request.seed_id,
        seed_topic=seed["topic"],
        seed_predicate=seed["predicate"],
        seed_metadata=seed["metadata"],
        dry_run=request.dry_run,
        max_attempts=request.max_attempts,
        timeout_seconds=request.timeout_seconds,
        judge_url=request.judge_url,
        model_routes=_resolve_model_routes(request.model_routes),
        artifact_paths=_build_tmp_artifact_paths(run_id, env=environ),
        safety_policy=build_local_safety_policy(env=environ),
        safety_receipt=build_local_safety_receipt(
            seed_id=request.seed_id,
            max_attempts=request.max_attempts,
            dry_run=request.dry_run,
            env=environ,
        ),
    )


def build_local_safety_policy(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = os.environ if env is None else env
    return {
        "status": "enforced",
        "seed_allowlist": [
            "fixture:first",
            "cve500:N",
            MODEL_ARMOR_BLOCK_SMOKE_SEED_ID,
        ],
        "arbitrary_seed_paths_allowed": False,
        "raw_seed_text_exposed": False,
        "run_id_pattern": RUN_ID_PATTERN.pattern,
        "model_route_roles": sorted(DEFAULT_MODEL_ROUTES),
        "model_route_values_must_be_non_empty": True,
        "max_attempts": {
            "min": 1,
            "max": 3,
            "live_default_max": _live_attempt_limit(environ),
        },
        "timeout_seconds": {
            "min": 1,
            "max": 300,
        },
        "live_execution": {
            "default_enabled": False,
            "requires_env": [
                "BARRED_ENABLE_FRESH_DEBATE=true",
                "BARRED_ENABLE_LIVE_FRESH_DEBATE=true",
                "BARRED_START_INTERNAL_DEBATE_STACK=true",
            ],
        },
    }


def build_local_safety_receipt(
    *,
    seed_id: str,
    max_attempts: int,
    dry_run: bool,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = os.environ if env is None else env
    return {
        "status": "enforced",
        "seed_id": seed_id,
        "seed_selector_allowed": True,
        "arbitrary_paths_allowed": False,
        "raw_seed_text_exposed": False,
        "max_attempts": max_attempts,
        "live_execution_flags_checked": not dry_run,
        "live_execution_enabled": _env_flag(
            "BARRED_ENABLE_LIVE_FRESH_DEBATE",
            environ=environ,
        ),
        "internal_debate_stack_enabled": should_start_internal_debate_stack(environ),
    }


def build_packaged_seed_manifest(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environ = os.environ if env is None else env
    fixture_path = _fixture_seed_path(env=environ)
    cve500_path = _cve500_seed_path(env=environ)
    return {
        "status": "ok",
        "sources": {
            "fixture": {
                "selector": "fixture:first",
                "selector_pattern": "fixture:first",
                "count": _count_jsonl_rows(fixture_path),
                "source_file": _source_file_for(fixture_path, env=environ),
                "sha256": _file_sha256(fixture_path),
            },
            "cve500": {
                "selector": "cve500:N",
                "selector_pattern": "cve500:<zero-based-index>",
                "count": _count_jsonl_rows(cve500_path),
                "source_file": "scenarios/debate/cve_seeds_500.jsonl",
                "sha256": _file_sha256(cve500_path),
            },
            "smoke": {
                "selector": MODEL_ARMOR_BLOCK_SMOKE_SEED_ID,
                "selector_pattern": MODEL_ARMOR_BLOCK_SMOKE_SEED_ID,
                "count": 1,
                "source_file": "packaged synthetic safety smoke seed",
                "sha256": _smoke_seed_sha256(),
            },
        },
        "selection_policy": {
            "allowlisted_only": True,
            "arbitrary_paths_allowed": False,
            "raw_seed_text_exposed": False,
        },
        "safety_policy": build_local_safety_policy(env=environ),
    }


def _planned_response(plan: FreshDebatePlan) -> dict[str, Any]:
    return {
        "status": "planned",
        "run_id": plan.run_id,
        "dry_run": True,
        "seed_id": plan.seed_id,
        "seed_metadata": plan.seed_metadata,
        "artifact_paths": plan.artifact_paths,
        "limits": {
            "max_attempts": plan.max_attempts,
            "timeout_seconds": plan.timeout_seconds,
        },
        "judge_url": plan.judge_url,
        "model_routes": plan.model_routes,
        "safety_policy": plan.safety_policy,
        "safety_receipt": plan.safety_receipt,
    }


def _validate_limits(max_attempts: int, timeout_seconds: int) -> None:
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3")
    if not 1 <= timeout_seconds <= 300:
        raise ValueError("timeout_seconds must be between 1 and 300")


def _validate_live_policy(
    plan: FreshDebatePlan,
    *,
    env: Mapping[str, str],
) -> dict[str, Any] | None:
    if not should_start_internal_debate_stack(env):
        return {
            "status": "attention_required",
            "run_id": plan.run_id,
            "error": "internal debate stack startup is disabled",
            "required_env": "BARRED_START_INTERNAL_DEBATE_STACK=true",
        }

    max_live_attempts = _live_attempt_limit(env)
    if plan.max_attempts > max_live_attempts:
        return {
            "status": "attention_required",
            "run_id": plan.run_id,
            "error": f"live fresh debate max_attempts must be <= {max_live_attempts}",
        }
    return None


def _live_attempt_limit(env: Mapping[str, str]) -> int:
    try:
        return int(env.get(MAX_LIVE_ATTEMPTS_ENV, "1"))
    except ValueError:
        return 1


def _normalize_or_create_run_id(run_id: str) -> str:
    resolved_run_id = run_id.strip() or _generated_run_id()
    if not RUN_ID_PATTERN.fullmatch(resolved_run_id):
        raise ValueError("run_id contains unsupported characters")
    return resolved_run_id


def _generated_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"fresh-demo-{timestamp}"


def _resolve_model_routes(model_routes: dict[str, str]) -> dict[str, str]:
    resolved = dict(DEFAULT_MODEL_ROUTES)
    for role, model in model_routes.items():
        if role not in resolved:
            raise ValueError(f"unsupported model route role: {role}")
        if not model.strip():
            raise ValueError(f"model route for {role} must be non-empty")
        resolved[role] = model
    return resolved


def _build_tmp_artifact_paths(
    run_id: str,
    *,
    env: Mapping[str, str],
) -> dict[str, str]:
    root = Path(env.get(TMP_ROOT_ENV, "/tmp/barred-fleet-runs"))
    run_dir = root / run_id
    return {
        "run_dir": str(run_dir),
        "input_path": str(run_dir / "training_corpus.jsonl"),
        "attempts_path": str(run_dir / "attempts.jsonl"),
        "deterministic_eval_result_path": str(
            run_dir / "deterministic_eval_result.json"
        ),
    }


async def _execute_existing_a2a_debate(
    plan: FreshDebatePlan,
    *,
    model_armor: dict[str, Any],
    agent_gateway: dict[str, Any],
) -> dict[str, Any]:
    from app.fresh_artifacts import build_fresh_run_report
    from app.tools import build_debate_case_payload, execute_debate_case

    payload = build_debate_case_payload(
        code=plan.seed_topic,
        predicate=plan.seed_predicate,
        run_id=plan.run_id,
        seed=42,
        mode="record",
        target_verdict="True",
        target_dimension="Security Invariants",
        num_rounds=1,
        max_refinements=plan.max_attempts,
        output_file=plan.artifact_paths["input_path"],
        attempts_path=plan.artifact_paths["attempts_path"],
        checkpoint_path=str(Path(plan.artifact_paths["run_dir"]) / "checkpoint.json"),
        record_path=str(Path(plan.artifact_paths["run_dir"]) / "record.json"),
        cassette_path=str(Path(plan.artifact_paths["run_dir"]) / "cassette.json"),
    )
    env = os.environ
    stack_context = nullcontext(
        DebateStackHandle(judge_url=plan.judge_url, started=False)
    )
    if should_start_internal_debate_stack(env):
        stack_context = start_internal_debate_stack(
            DebateStackConfig.from_env(
                env,
                judge_url=plan.judge_url,
                model_routes=plan.model_routes,
            )
        )

    with stack_context as stack:
        result = await execute_debate_case(payload=payload, judge_url=stack.judge_url)
    artifact_paths = {
        **plan.artifact_paths,
        **(result.get("artifact_paths") or {}),
    }
    return {
        "status": result.get("status", "completed"),
        "run_id": plan.run_id,
        "execution": {
            "fresh": True,
            "dry_run": False,
            "seed_id": plan.seed_id,
            "seed_metadata": plan.seed_metadata,
            "artifact_scope": "tmp",
            "timeout_seconds": plan.timeout_seconds,
            "judge_url": stack.judge_url,
            "internal_stack_started": stack.started,
        },
        "artifact_paths": artifact_paths,
        "debate_result": result,
        "fresh_report": build_fresh_run_report(
            run_id=plan.run_id,
            artifact_paths=artifact_paths,
            seed_id=plan.seed_id,
            seed_metadata=plan.seed_metadata,
            model_routes=plan.model_routes,
            safety_policy=plan.safety_policy,
            safety_receipt=plan.safety_receipt,
            model_armor=model_armor,
            agent_gateway=agent_gateway,
            max_attempts=plan.max_attempts,
        ),
    }


def _resolve_seed(seed_id: str, *, env: Mapping[str, str]) -> dict[str, Any]:
    if seed_id in ALLOWED_FIXTURE_SEEDS:
        payload = _load_fixture_seed(seed_id)
        return _seed_record(
            seed_id=seed_id,
            payload=payload,
            source="fixture",
            source_file=_source_file_for(_fixture_seed_path(), env=env),
            index=0,
        )

    if seed_id == MODEL_ARMOR_BLOCK_SMOKE_SEED_ID:
        return _seed_record(
            seed_id=seed_id,
            payload=_load_model_armor_block_smoke_seed(),
            source="smoke",
            source_file="packaged synthetic safety smoke seed",
            index=0,
        )

    cve500_index = _parse_cve500_seed_index(seed_id)
    if cve500_index is None:
        raise ValueError(f"unknown seed_id: {seed_id}")
    payload = _load_cve500_seed(cve500_index, env=env)
    return _seed_record(
        seed_id=seed_id,
        payload=payload,
        source="cve500",
        source_file="scenarios/debate/cve_seeds_500.jsonl",
        index=cve500_index,
    )


def _parse_cve500_seed_index(seed_id: str) -> int | None:
    if not seed_id.startswith(CVE500_SEED_PREFIX):
        return None
    raw_index = seed_id.removeprefix(CVE500_SEED_PREFIX)
    if not raw_index.isdecimal():
        raise ValueError(f"unknown seed_id: {seed_id}")
    return int(raw_index)


def _load_cve500_seed(index: int, *, env: Mapping[str, str]) -> dict[str, Any]:
    seed_path = _cve500_seed_path(env=env)
    if not seed_path.exists():
        raise ValueError(f"allowlisted seed file not found: {seed_path}")
    with seed_path.open("r", encoding="utf-8") as seed_file:
        for current_index, line in enumerate(seed_file):
            if current_index == index:
                return _load_json_seed_line(line, seed_path=seed_path)
    raise ValueError(f"{seed_path} does not contain seed index {index}")


def _cve500_seed_path(*, env: Mapping[str, str]) -> Path:
    runtime_root = Path(env.get(RUNTIME_ROOT_ENV, Path(__file__).resolve().parents[1]))
    return runtime_root / "scenarios" / "debate" / "cve_seeds_500.jsonl"


def _seed_record(
    *,
    seed_id: str,
    payload: dict[str, Any],
    source: str,
    source_file: str,
    index: int,
) -> dict[str, Any]:
    topic = str(payload["topic"])
    predicate = str(payload["predicate"])
    return {
        "topic": topic,
        "predicate": predicate,
        "metadata": {
            "seed_id": seed_id,
            "source": source,
            "source_file": source_file,
            "index": index,
            "language": payload.get("language", ""),
            "original_safety": payload.get("original_safety", ""),
            "predicate_sha256": sha256(predicate.encode("utf-8")).hexdigest(),
            "topic_sha256": sha256(topic.encode("utf-8")).hexdigest(),
        },
    }


def _source_file_for(path: Path, *, env: Mapping[str, str]) -> str:
    runtime_root = Path(env.get(RUNTIME_ROOT_ENV, Path(__file__).resolve().parents[1]))
    try:
        return path.relative_to(runtime_root).as_posix()
    except ValueError:
        return path.name


def _load_json_seed_line(line: str, *, seed_path: Path) -> dict[str, Any]:
    stripped = line.strip()
    if not stripped:
        raise ValueError(f"{seed_path} seed line is empty")
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError(f"{seed_path} must contain JSON objects")
    if "topic" not in payload or "predicate" not in payload:
        raise ValueError(f"{seed_path} seed must contain topic and predicate")
    return payload


def _load_fixture_seed(seed_id: str) -> dict[str, Any]:
    if seed_id != "fixture:first":
        raise ValueError(f"unknown seed_id: {seed_id}")

    seed_path = _fixture_seed_path()
    with seed_path.open("r", encoding="utf-8") as seed_file:
        for line in seed_file:
            if line.strip():
                return _load_json_seed_line(line, seed_path=seed_path)
    raise ValueError(f"{seed_path} does not contain any seeds")


def _load_model_armor_block_smoke_seed() -> dict[str, Any]:
    return {
        "language": "text",
        "original_safety": "blocked_smoke",
        "topic": (
            "Synthetic BARRED-Fleet safety smoke seed. "
            "This input is not a benchmark sample and must never be accepted "
            "into a corpus. Visit http://malware.testing.google.test/testing/"
            "malware/ only as inert text for content-safety screening."
        ),
        "predicate": (
            "Reject before live debate if Model Armor flags the packaged "
            "malicious URI smoke text."
        ),
    }


def _smoke_seed_sha256() -> str:
    payload = _load_model_armor_block_smoke_seed()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _fixture_seed_path(*, env: Mapping[str, str] | None = None) -> Path:
    environ = os.environ if env is None else env
    configured_path = environ.get(SEEDS_PATH_ENV, "")
    if configured_path:
        return Path(configured_path)
    runtime_root = Path(environ.get(RUNTIME_ROOT_ENV, Path(__file__).resolve().parents[1]))
    return runtime_root / "scenarios" / "debate" / "cve_seeds_test.jsonl"


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as seed_file:
        return sum(1 for line in seed_file if line.strip())


def _file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return sha256(path.read_bytes()).hexdigest()


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
