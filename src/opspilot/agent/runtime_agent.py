"""Agent Runtime entrypoint; local M6 discovery remains unchanged."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from google.adk.agents import InvocationContext
from google.adk.sessions import InMemorySessionService
from google.genai import types
from vertexai import agent_engines
from vertexai.agent_engines import _utils

from opspilot.agent.runtime import (
    RuntimeHandler,
    bind_external_runtime_identity,
    create_runtime_root_agent,
    run_live_runtime_investigation,
)


class OpsPilotRuntimeApp(agent_engines.AdkApp):
    """Narrow ADK application surface used by Gemini Enterprise."""

    def register_operations(self) -> dict[str, list[str]]:
        return {"async_stream": ["streaming_agent_run_with_events"]}

    async def streaming_agent_run_with_events(
        self, request_json: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute the bounded ADK agent without the provider's lossy stream wrapper."""

        request = json.loads(request_json)
        user_id = request.get("user_id") or request.get("userId")
        session_id = request.get("session_id") or request.get("sessionId")
        effective_user_id = str(user_id) if user_id else "default-user-id"
        content = types.Content.model_validate(request["message"])
        session_service = create_ephemeral_session_service()
        session = await session_service.create_session(
            app_name=self._app_name(), user_id=effective_user_id
        )
        agent = self._tmpl_attrs["agent"]
        context = InvocationContext(
            session_service=session_service,
            invocation_id=f"e-{uuid4()}",
            agent=agent,
            user_content=content,
            session=session,
        )
        try:
            events: list[dict[str, Any]] = []
            with bind_external_runtime_identity(
                user_id=str(user_id) if user_id else None,
                session_id=str(session_id) if session_id else None,
            ):
                async for event in agent._run_async_impl(context):
                    converted = _utils.dump_event_for_json(event)
                    converted["invocation_id"] = converted.get("invocation_id", "")
                    events.append(converted)
            if events:
                yield {"events": events, "session_id": session.id}
                yield {"events": []}
        finally:
            await session_service.delete_session(
                app_name=self._app_name(),
                user_id=effective_user_id,
                session_id=session.id,
            )


def create_ephemeral_session_service() -> InMemorySessionService:
    """Keep ADK event state ephemeral; the API owns minimal durable conversation context."""
    return InMemorySessionService()  # type: ignore[no-untyped-call]


def create_runtime_app(
    *,
    handler: RuntimeHandler = run_live_runtime_investigation,
) -> OpsPilotRuntimeApp:
    """Create the bounded conversational Enterprise Runtime application."""
    app = OpsPilotRuntimeApp(
        agent=create_runtime_root_agent(handler=handler),
        app_name="opspilot_runtime",
        session_service_builder=create_ephemeral_session_service,
    )
    return app


root_agent = create_runtime_app()
