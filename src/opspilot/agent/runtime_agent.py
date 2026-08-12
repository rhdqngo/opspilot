"""Agent Runtime entrypoint; local M6 discovery remains unchanged."""

from google.adk.sessions import InMemorySessionService
from vertexai import agent_engines

from opspilot.agent.runtime import (
    RuntimeHandler,
    create_runtime_root_agent,
    run_live_runtime_investigation,
)


class OpsPilotRuntimeApp(agent_engines.AdkApp):
    """Narrow ADK application surface used by Gemini Enterprise."""

    def register_operations(self) -> dict[str, list[str]]:
        return {"async_stream": ["streaming_agent_run_with_events"]}


def create_ephemeral_session_service() -> InMemorySessionService:
    """Keep the single-turn MVP independent of managed Agent Platform Sessions."""
    return InMemorySessionService()  # type: ignore[no-untyped-call]


def create_runtime_app(
    *,
    handler: RuntimeHandler = run_live_runtime_investigation,
) -> OpsPilotRuntimeApp:
    """Create the fixed-scope Enterprise Runtime application."""
    return OpsPilotRuntimeApp(
        agent=create_runtime_root_agent(handler=handler),
        app_name="opspilot_runtime",
        session_service_builder=create_ephemeral_session_service,
    )


root_agent = create_runtime_app()
