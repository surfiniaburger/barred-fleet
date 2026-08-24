from __future__ import annotations

import socket
import time
from pathlib import Path

from app.debate_stack import DebateStackConfig, start_internal_debate_stack

STACK_PORTS = (9009, 9018, 9019, 9020)


def main() -> int:
    occupied = [port for port in STACK_PORTS if _port_open(port)]
    if occupied:
        print(f"[verify-packaged-stack] ports already occupied: {occupied}")
        return 1

    runtime_root = Path(__file__).resolve().parents[1]
    config = DebateStackConfig.from_env(
        {
            "BARRED_DEBATE_RUNTIME_ROOT": str(runtime_root),
            "BARRED_DEBATE_STACK_STARTUP_TIMEOUT": "25",
        },
        judge_url="http://127.0.0.1:9009",
        model_routes={
            "generator": "ollama/gemma4:31b-cloud",
            "judge": "ollama/gpt-oss:120b-cloud",
            "verifier": "ollama/gpt-oss:120b-cloud",
        },
    )

    with start_internal_debate_stack(config) as stack:
        print(
            {
                "started": stack.started,
                "judge_url": stack.judge_url,
                "runtime_root": str(runtime_root),
            }
        )

    lingering = _wait_for_closed_ports()
    if lingering:
        print(f"[verify-packaged-stack] ports still occupied after cleanup: {lingering}")
        return 1

    print("[verify-packaged-stack] packaged stack startup and cleanup passed")
    return 0


def _wait_for_closed_ports() -> list[int]:
    deadline = time.monotonic() + 5
    lingering = [port for port in STACK_PORTS if _port_open(port)]
    while lingering and time.monotonic() < deadline:
        time.sleep(0.25)
        lingering = [port for port in STACK_PORTS if _port_open(port)]
    return lingering


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    raise SystemExit(main())
