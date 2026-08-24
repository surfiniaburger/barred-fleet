from typing import Any
from uuid import uuid4

import httpx
from a2a.client import (
    A2ACardResolver,
    ClientConfig,
    ClientFactory,
)
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    StreamResponse,
    Task,
    TaskState,
)

DEFAULT_TIMEOUT = 1200


def create_message(
    *,
    role: Role = Role.ROLE_USER,
    text: str,
    context_id: str | None = None,
) -> Message:
    return Message(
        role=role,
        parts=[Part(text=text)],
        message_id=uuid4().hex,
        context_id=context_id
    )


def create_send_request(
    *,
    text: str,
    context_id: str | None = None,
) -> SendMessageRequest:
    return SendMessageRequest(
        message=create_message(text=text, context_id=context_id),
        configuration=SendMessageConfiguration(),
    )


def merge_parts(parts: list[Part]) -> str:
    chunks = []
    for part in parts:
        if part.text:
            chunks.append(part.text)
        elif part.data:
            chunks.append(str(part.data))
    return "\n".join(chunks)


def task_state_name(task: Task) -> str:
    name = TaskState.Name(task.status.state)
    return name.removeprefix("TASK_STATE_").lower()


def merge_stream_response(event: StreamResponse) -> dict[str, Any]:
    outputs = {
        "response": "",
        "context_id": None,
    }
    if event.HasField("message"):
        msg = event.message
        outputs["context_id"] = msg.context_id
        outputs["response"] += merge_parts(msg.parts)
        return outputs

    if event.HasField("task"):
        task = event.task
        outputs["context_id"] = task.context_id
        outputs["status"] = task_state_name(task)
        msg = task.status.message
        if msg:
            outputs["response"] += merge_parts(msg.parts)
        if task.artifacts:
            for artifact in task.artifacts:
                outputs["response"] += merge_parts(artifact.parts)
    return outputs

async def send_message(
    message: str,
    base_url: str,
    context_id: str | None = None,
    streaming=False,
    consumer: Any | None = None,
):
    """Returns dict with context_id, response and status (if exists)"""
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()
        config = ClientConfig(
            httpx_client=httpx_client,
            streaming=streaming,
        )
        factory = ClientFactory(config)
        client = factory.create(agent_card)
        if consumer:
            await client.add_event_consumer(consumer)

        outbound_msg = create_send_request(text=message, context_id=context_id)
        last_event = None

        # if streaming == False, only one event is generated
        async for event in client.send_message(outbound_msg):
            last_event = event

        if last_event is None:
            return {"response": "", "context_id": None}
        return merge_stream_response(last_event)
