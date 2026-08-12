"""Agent Runtime entrypoint; local M6 discovery remains unchanged."""

from vertexai import agent_engines

from opspilot.agent.runtime import create_runtime_root_agent


class OpsPilotRuntimeApp(agent_engines.AdkApp):
    """Narrow ADK application surface used by Gemini Enterprise."""

    def register_operations(self) -> dict[str, list[str]]:
        return {"async_stream": ["streaming_agent_run_with_events"]}


root_agent = OpsPilotRuntimeApp(
    agent=create_runtime_root_agent(),
    app_name="opspilot_runtime",
)
