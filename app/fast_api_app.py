# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import logging
import os
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.typing import Feedback
from app.demo import build_demo_html, build_demo_report
from app.fresh_debate import (
    FreshDebateRequest,
    build_packaged_seed_manifest,
    run_fresh_debate_async,
)
from app.gepa_memory import build_gepa_memory_preview
from app.memory_bank import EnterpriseMemoryBank
from app.run_lifecycle import (
    build_product_run_report,
    create_product_run,
    get_product_run,
    queue_product_run,
    run_queued_product_run,
)

load_dotenv()
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


TRACE_TO_CLOUD = _env_flag("BARRED_FLEET_OTEL_TO_CLOUD")
local_logger = logging.getLogger(__name__)
cloud_logger = None
if TRACE_TO_CLOUD:
    from google.cloud import logging as google_cloud_logging

    logging_client = google_cloud_logging.Client()
    cloud_logger = logging_client.logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    trace_to_cloud=TRACE_TO_CLOUD,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "barred-fleet"
app.description = "API for interacting with the Agent barred-fleet"


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    if cloud_logger is not None:
        cloud_logger.log_struct(feedback.model_dump(), severity="INFO")
    else:
        local_logger.info("feedback=%s", feedback.model_dump())
    return {"status": "success"}


@app.get("/demo", response_class=HTMLResponse)
def demo_page() -> HTMLResponse:
    """Serve the read-only BARRED-Fleet hackathon demo surface."""
    return HTMLResponse(build_demo_html(service_title=app.title))


@app.get("/demo/report")
def demo_report(run_id: str = "pilot-v1-calibrated-pecan") -> dict:
    """Return the deterministic BARRED-Fleet demo report."""
    return build_demo_report(run_id=run_id)


@app.post("/runs/fresh-demo")
async def fresh_demo_run(request: FreshDebateRequest) -> dict:
    """Plan or execute a tiny fresh BARRED debate run."""
    return await run_fresh_debate_async(request)


@app.post("/runs")
async def create_run(request: FreshDebateRequest, background_tasks: BackgroundTasks) -> dict:
    """Create a product-shaped BARRED run lifecycle record."""
    if request.async_mode and not request.dry_run:
        return queue_product_run(
            request,
            schedule=lambda queued_request, kwargs: background_tasks.add_task(
                run_queued_product_run,
                queued_request,
                **kwargs,
            ),
        )
    return await create_product_run(request)


@app.get("/seeds/manifest")
def seed_manifest() -> dict:
    """Return allowlisted packaged seed source metadata."""
    return build_packaged_seed_manifest()


@app.get("/memory/gepa/preview")
def gepa_memory_preview() -> dict:
    """Return a read-only redacted GEPA empirical memory preview."""
    return build_gepa_memory_preview(env=os.environ)


def get_memory_bank(request: Request) -> EnterpriseMemoryBank:
    """Provide a cached EnterpriseMemoryBank instance per application process."""
    from app.memory_bank import EnterpriseMemoryBank

    bank = getattr(request.app.state, "memory_bank", None)
    if bank is None:
        bank = EnterpriseMemoryBank()
        request.app.state.memory_bank = bank
    return bank


@app.get("/memory/gepa/query")
def gepa_memory_query(
    taxonomy: str = "memory_safety",
    bank: EnterpriseMemoryBank = Depends(get_memory_bank),
) -> dict:
    """Query the Enterprise Memory Bank for an active specialized Pareto directive."""
    return bank.get_specialist(taxonomy=taxonomy)



@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    """Return product-shaped BARRED run lifecycle metadata."""
    return get_product_run(run_id)


@app.get("/runs/{run_id}/report")
def get_run_report(run_id: str) -> dict:
    """Return a read-only BARRED product run report."""
    return build_product_run_report(run_id)


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
