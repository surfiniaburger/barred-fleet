from __future__ import annotations

from fastapi import FastAPI

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH


def build_a2a_app(agent_card: AgentCard, executor) -> FastAPI:
    app = FastAPI()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(
            agent_card,
            card_url=AGENT_CARD_WELL_KNOWN_PATH,
        ),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler,
            rpc_url="/",
            enable_v0_3_compat=True,
        ),
    )
    return app
