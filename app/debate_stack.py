from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STACK_FLAG = "BARRED_START_INTERNAL_DEBATE_STACK"
RUNTIME_ROOT_ENV = "BARRED_DEBATE_RUNTIME_ROOT"
SCENARIO_PATH_ENV = "BARRED_DEBATE_SCENARIO_PATH"
STARTUP_TIMEOUT_ENV = "BARRED_DEBATE_STACK_STARTUP_TIMEOUT"
DEFAULT_SCENARIO_PATH = "scenarios/debate/barred_test.toml"
DEFAULT_JUDGE_URL = "http://127.0.0.1:9009"
DEFAULT_MODEL_ROUTES = {
    "generator": "vertex_ai/gemini-3.5-flash-lite",
    "judge": "vertex_ai/gemini-3.6-flash",
    "verifier": "vertex_ai/gemini-3.6-flash",
}


class DebateStackStartupError(RuntimeError):
    pass


@dataclass(frozen=True)
class DebateStackConfig:
    runtime_root: Path
    scenario_path: Path | None = None
    judge_url: str = DEFAULT_JUDGE_URL
    startup_timeout_seconds: int = 30
    model_routes: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_MODEL_ROUTES)
    )
    show_logs: bool = False

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str],
        *,
        judge_url: str,
        model_routes: Mapping[str, str],
    ) -> DebateStackConfig:
        runtime_root = Path(env.get(RUNTIME_ROOT_ENV, _default_runtime_root()))
        configured_scenario = env.get(SCENARIO_PATH_ENV, DEFAULT_SCENARIO_PATH)
        timeout_text = env.get(STARTUP_TIMEOUT_ENV, "30")
        return cls(
            runtime_root=runtime_root,
            scenario_path=runtime_root / configured_scenario,
            judge_url=judge_url,
            startup_timeout_seconds=_parse_startup_timeout(timeout_text),
            model_routes=model_routes,
            show_logs=_env_flag("BARRED_DEBATE_STACK_SHOW_LOGS", env),
        )


@dataclass(frozen=True)
class DebateStackHandle:
    judge_url: str
    started: bool


ProcessFactory = Callable[..., Any]
ReadinessProbe = Callable[[str, int], bool]


def should_start_internal_debate_stack(env: Mapping[str, str]) -> bool:
    return _env_flag(STACK_FLAG, env)


def build_debate_stack_command(config: DebateStackConfig) -> list[str]:
    scenario_path = config.scenario_path or config.runtime_root / DEFAULT_SCENARIO_PATH
    return [
        sys.executable,
        str(config.runtime_root / "src" / "agentbeats" / "run_scenario.py"),
        str(scenario_path),
        "--serve-only",
    ]


def build_debate_stack_env(
    config: DebateStackConfig,
    *,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    python_paths = [
        str(config.runtime_root / "src"),
        str(config.runtime_root),
    ]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        python_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["JUDGE_MODEL"] = config.model_routes.get("judge", DEFAULT_MODEL_ROUTES["judge"])
    generator_model = config.model_routes.get("generator", DEFAULT_MODEL_ROUTES["generator"])
    env["DEBATER_MODEL"] = generator_model
    env["GENERATOR_MODEL"] = generator_model
    env["VERIFIER_MODEL"] = config.model_routes.get(
        "verifier", DEFAULT_MODEL_ROUTES["verifier"]
    )
    if _uses_vertex_gemini(config.model_routes):
        env.setdefault("VERTEXAI_PROJECT", env.get("GOOGLE_CLOUD_PROJECT", ""))
        env.setdefault(
            "VERTEXAI_LOCATION",
            env.get("GOOGLE_CLOUD_LOCATION") or env.get("GOOGLE_CLOUD_REGION", ""),
        )
        env.setdefault("LLM_SAMPLING_PROFILE", "vertex_gemini")
    else:
        env.setdefault("LLM_SAMPLING_PROFILE", "ollama_gemma4")
    return env


def _uses_vertex_gemini(model_routes: Mapping[str, str]) -> bool:
    return any(
        str(model).lower().startswith("vertex_ai/gemini")
        for model in model_routes.values()
    )


@contextmanager
def start_internal_debate_stack(
    config: DebateStackConfig,
    *,
    process_factory: ProcessFactory = subprocess.Popen,
    readiness_probe: ReadinessProbe | None = None,
) -> Iterator[DebateStackHandle]:
    probe = readiness_probe or _wait_for_judge
    process = process_factory(
        build_debate_stack_command(config),
        cwd=str(config.runtime_root),
        env=build_debate_stack_env(config),
        stdout=None if config.show_logs else subprocess.DEVNULL,
        stderr=None if config.show_logs else subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    try:
        if process.poll() is not None:
            raise DebateStackStartupError(
                f"internal debate stack exited early with code {process.poll()}"
            )
        if not probe(config.judge_url, config.startup_timeout_seconds):
            raise DebateStackStartupError(
                f"internal debate stack did not become ready at {config.judge_url}"
            )
        yield DebateStackHandle(judge_url=config.judge_url, started=True)
    finally:
        _terminate_process(process)


def _wait_for_judge(judge_url: str, timeout_seconds: int) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(judge_url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except urllib.error.HTTPError as exc:
            if 200 <= exc.code < 500:
                return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    return False


def _terminate_process(process: Any) -> None:
    if process.poll() is not None:
        return
    _terminate_process_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _terminate_process_group(process, signal.SIGKILL)
        process.wait(timeout=5)


def _terminate_process_group(process: Any, sig: int) -> None:
    pid = getattr(process, "pid", None)
    if isinstance(pid, int):
        try:
            os.killpg(pid, sig)
            return
        except ProcessLookupError:
            return
    if sig == signal.SIGTERM:
        process.terminate()
    else:
        process.kill()


def _default_runtime_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _parse_startup_timeout(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{STARTUP_TIMEOUT_ENV} must be an integer") from exc
    if not 1 <= parsed <= 120:
        raise ValueError(f"{STARTUP_TIMEOUT_ENV} must be between 1 and 120")
    return parsed


def _env_flag(name: str, env: Mapping[str, str]) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
