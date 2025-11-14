# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Agent Framework integration for Teams conversations."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from agent_framework import ChatAgent, ChatMessageStore, MCPStreamableHTTPTool
from agent_framework._threads import AgentThread
from agent_framework._types import AgentRunResponse
from agent_framework.azure import AzureOpenAIChatClient

logger = logging.getLogger(__name__)


class AgentService:
    """Wraps Agent Framework primitives for reuse inside dialogs/bots."""

    def __init__(self) -> None:
        # self._tool = self._build_mcp_tool()
        self._tools = self.get_tools()
        self._chat_client = self._build_chat_client()
        self._agent = self._build_agent()

    def get_tools(self):
        return []

    def _build_mcp_tool(self) -> MCPStreamableHTTPTool:
        tool_name = os.getenv("MCP_TOOL_NAME", "MS Graph")
        tool_url = os.getenv("MCP_TOOL_URL", "http://localhost:8000/mcp")
        approval_mode_env = os.getenv("MCP_APPROVAL_MODE")

        approval_mode: Any
        if approval_mode_env in {"always_require", "never_require"}:
            approval_mode = approval_mode_env  # type: ignore[assignment]
        else:
            approval_mode = None

        logger.info("Configuring MCP tool '%s' -> %s", tool_name, tool_url)

        return MCPStreamableHTTPTool(
            name=tool_name,
            url=tool_url,
            approval_mode=approval_mode,
        )

    def _build_chat_client(self) -> AzureOpenAIChatClient:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment_name = os.getenv("AZURE_OPENAI_MODEL", "")
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")

        logger.info(
            "Initializing Azure OpenAI chat client (deployment=%s)", deployment_name
        )

        return AzureOpenAIChatClient(
            endpoint=endpoint or None,
            deployment_name=deployment_name or None,
            api_key=api_key or None,
            api_version=api_version or None,
        )

    def _build_agent(self) -> ChatAgent:
        agent_name = os.getenv("TEAMS_AGENT_NAME", "teams_agent")
        instructions = os.getenv(
            "TEAMS_AGENT_INSTRUCTIONS",
            "You are a helpful Teams assistant. Use the available MCP tools to ground every answer.",
        )
        temperature_env = os.getenv("TEAMS_AGENT_TEMPERATURE")
        temperature = float(temperature_env) if temperature_env else None

        logger.info("Creating Agent Framework chat agent '%s'", agent_name)

        return ChatAgent(
            chat_client=self._chat_client,
            name=agent_name,
            instructions=instructions,
            tools=self._tools,
            chat_message_store_factory=ChatMessageStore,
            temperature=temperature,
        )

    async def run(
        self,
        prompt: str,
        tools: Optional[Any] = None,
        *,
        thread_state: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
    ) -> Tuple[AgentRunResponse, Dict[str, Any]]:
        """Execute the agent with the supplied prompt and thread context.

        Returns the AgentRunResponse and the updated serialized thread state so callers
        can persist it alongside their conversation state.
        """
        if tools is None:
            tools = self._tools
        if not prompt:
            raise ValueError("Prompt cannot be empty when invoking the agent.")

        thread = await self._deserialize_thread(thread_state)
        if thread_state:
            logger.debug(
                "Restored agent thread with %s messages.",
                len(
                    thread_state.get("chat_message_store_state", {}).get("messages", [])
                )
                if isinstance(thread_state, dict)
                else "?",
            )

        logger.debug("Invoking agent with prompt='%s' (user=%s)", prompt, user)

        response = await self._agent.run(
            prompt,
            thread=thread,
            user=user,
            tools=tools,
        )

        serialized = await thread.serialize()
        message_count = len(
            serialized.get("chat_message_store_state", {}).get("messages", [])
        )
        logger.debug("Serialized agent thread now has %s messages.", message_count)
        return response, serialized

    async def _deserialize_thread(
        self, thread_state: Optional[Dict[str, Any]]
    ) -> AgentThread:
        if not thread_state:
            return self._agent.get_new_thread()

        try:
            return await self._agent.deserialize_thread(thread_state)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to deserialize agent thread; starting a new one.")
            return self._agent.get_new_thread()
