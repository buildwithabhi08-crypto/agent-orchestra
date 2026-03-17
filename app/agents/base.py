"""Base agent class with skills loading and tool binding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.config import get_settings
from app.llm import get_llm_for_agent
from app.models.schemas import AgentRole


class BaseAgent:
    """Base class for all specialized agents."""

    role: AgentRole
    name: str
    description: str
    system_prompt: str
    tools: list[BaseTool]

    def __init__(self) -> None:
        self.llm: BaseChatModel = get_llm_for_agent(self.role.value)
        self.skill_content: str = self._load_skill()
        self._full_system_prompt = self._build_system_prompt()

        # Bind tools to the LLM if available
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = self.llm

    def _load_skill(self) -> str:
        """Load SKILL.md file for this agent if it exists."""
        settings = get_settings()
        skill_dir = Path(settings.skills_dir) / self.role.value
        skill_file = skill_dir / "SKILL.md"

        if skill_file.exists():
            content = skill_file.read_text()
            # Parse frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        metadata = yaml.safe_load(parts[1])
                        return f"Skill: {metadata.get('name', self.name)}\n\n{parts[2].strip()}"
                    except yaml.YAMLError:
                        pass
            return content
        return ""

    def _build_system_prompt(self) -> str:
        """Build the full system prompt including skills."""
        prompt = self.system_prompt

        if self.skill_content:
            prompt += f"\n\n## Your Skills & Expertise\n{self.skill_content}"

        if self.tools:
            tool_names = [t.name for t in self.tools]
            prompt += f"\n\n## Available Tools\nYou have access to: {', '.join(tool_names)}"
            prompt += "\nUse these tools proactively to accomplish your tasks."

        return prompt

    async def invoke(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Execute a task with this agent.

        Args:
            task: The task description for this agent.
            context: Optional context from other agents or the orchestrator.
        """
        messages = [SystemMessage(content=self._full_system_prompt)]

        if context:
            context_str = "\n".join(f"- **{k}**: {v}" for k, v in context.items())
            messages.append(
                HumanMessage(content=f"## Context from other agents:\n{context_str}")
            )

        messages.append(HumanMessage(content=task))

        # Iterative tool-calling loop
        max_iterations = 10
        for _ in range(max_iterations):
            response = await self.llm_with_tools.ainvoke(messages)

            if not isinstance(response, AIMessage) or not response.tool_calls:
                # No more tool calls, return the final response
                return response.content if isinstance(response, AIMessage) else str(response)

            # Process tool calls
            messages.append(response)
            for tool_call in response.tool_calls:
                tool_result = await self._execute_tool(tool_call)
                from langchain_core.messages import ToolMessage

                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call["id"],
                    )
                )

        # Final response after max iterations
        final = await self.llm.ainvoke(messages)
        return final.content if isinstance(final, AIMessage) else str(final)

    async def _execute_tool(self, tool_call: dict[str, Any]) -> str:
        """Execute a tool call and return the result."""
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(tool_args)
                    return str(result)
                except Exception as e:
                    return f"Tool error ({tool_name}): {str(e)}"

        return f"Error: Tool '{tool_name}' not found."

    def get_info(self) -> dict[str, Any]:
        """Return agent info for the API."""
        return {
            "role": self.role.value,
            "name": self.name,
            "description": self.description,
            "model": self.llm.__class__.__name__,
            "tools": [t.name for t in self.tools],
            "has_skills": bool(self.skill_content),
        }
