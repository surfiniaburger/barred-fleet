from abc import abstractmethod
from uuid import uuid4

from pydantic import ValidationError

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    Message,
    Part,
    Role,
    Task,
    TaskStatus,
    TaskState,
)
from a2a.utils.errors import (
    InvalidParamsError,
    UnsupportedOperationError,
)

from agentbeats.models import EvalRequest


def new_agent_text_message(text: str, context_id: str | None = None) -> Message:
    return Message(
        message_id=uuid4().hex,
        context_id=context_id,
        role=Role.ROLE_AGENT,
        parts=[Part(text=text)],
    )


def new_task(message: Message) -> Task:
    context_id = message.context_id or uuid4().hex
    return Task(
        id=message.task_id or uuid4().hex,
        context_id=context_id,
        status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
        history=[message],
    )


class GreenAgent:

    @abstractmethod
    async def run_eval(self, request: EvalRequest, updater: TaskUpdater) -> None:
        pass

    @abstractmethod
    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        pass


class GreenExecutor(AgentExecutor):

    def __init__(self, green_agent: GreenAgent):
        self.agent = green_agent

    @staticmethod
    def _is_terminal_state_error(exc: BaseException) -> bool:
        return "terminal state" in str(exc).lower()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        request_text = context.get_user_input()
        try:
            req: EvalRequest = EvalRequest.model_validate_json(request_text)
            ok, msg = self.agent.validate_request(req)
            if not ok:
                raise InvalidParamsError(message=msg)
        except ValidationError as e:
            raise InvalidParamsError(message=e.json())

        msg = context.message
        if msg:
            task = new_task(msg)
            await event_queue.enqueue_event(task)
        else:
            raise InvalidParamsError(message="Missing message.")

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            new_agent_text_message(f"Starting assessment.\n{req.model_dump_json()}", context_id=context.context_id)
        )

        try:
            await self.agent.run_eval(req, updater)
            try:
                await updater.complete()
            except RuntimeError as complete_err:
                if not self._is_terminal_state_error(complete_err):
                    raise
        except Exception as e:
            print(f"Agent error: {e}")
            try:
                await updater.failed(new_agent_text_message(f"Agent error: {e}", context_id=context.context_id))
            except RuntimeError as failed_err:
                if not self._is_terminal_state_error(failed_err):
                    raise
            raise InternalError(message=str(e))

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise UnsupportedOperationError()
