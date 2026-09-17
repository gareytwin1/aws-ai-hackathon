"""AgentCore entrypoint for the Pipeline Leak Detection Agent."""

import sys
import os
from pathlib import Path
from typing import Any
from collections import OrderedDict

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Add the project root to the path so we can import existing modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools import ALL_TOOLS
from agent import SYSTEM_PROMPT

app = BedrockAgentCoreApp()
log = app.logger

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-east-1",
)


def agent_factory():
    """Create a session-aware agent factory with LRU cache."""
    cache = OrderedDict()

    def get_or_create_agent(session_id):
        if session_id in cache:
            cache.move_to_end(session_id)
            return cache[session_id]
        if len(cache) >= 128:
            cache.popitem(last=False)
        cache[session_id] = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            conversation_manager=NullConversationManager(),
        )
        return cache[session_id]

    return get_or_create_agent


get_or_create_agent = agent_factory()


def _extract_prompt(payload: dict):
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "messages" in payload:
        return payload["messages"]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


@app.entrypoint
async def invoke(payload, context):
    """Main AgentCore entrypoint -- streams agent responses."""
    log.info("Invoking Pipeline Leak Detection Agent...")

    session_id = getattr(context, "session_id", "default-session")
    agent = get_or_create_agent(session_id)

    prompt = _extract_prompt(payload)

    async for event in agent.stream_async(prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
