"""Orchestrator Agent - the boss that manages all other agents."""

from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.llm import get_llm_for_agent
from app.models.schemas import AgentRole, SubTask, TaskPlan, TaskStatus

PLANNING_PROMPT = """You are the Orchestrator — the boss of a multi-agent team building SaaS products.

## Your Team
1. **Senior Developer** (developer) - Builds prototypes, writes code, manages technical implementation
2. **Market Researcher** (market_researcher) - Discovers pain points, identifies booming ideas, product research
3. **Competitive Analyst** (competitive_analyst) - Analyzes competitors, pricing, features, identifies gaps
4. **Senior Marketing Strategist** (marketing) - Marketing strategy, social media content, brand positioning
5. **Pre-validation Specialist** (prevalidation) - Validates ideas before building, demand analysis
6. **Lead Generation Specialist** (lead_gen) - Identifies customers, outreach strategies, lead lists

## Your Responsibilities
- Understand the user's task and break it into sub-tasks
- Assign sub-tasks to the right agents based on their expertise
- Identify which tasks can run in parallel vs. which need to be sequential
- Define checkpoints where user approval is needed
- Coordinate handoffs between agents (one agent's output feeds another's input)
- Review agent outputs and suggest improvements
- Compile the final deliverable

## Task Decomposition Rules
1. Always start with research/validation before building
2. Market research and competitive analysis can run in PARALLEL
3. Pre-validation should come AFTER initial research
4. Development starts AFTER validation is approved
5. Marketing and lead gen can run in PARALLEL after the product direction is clear
6. Add a checkpoint after research phase and after validation phase

## Output Format
You MUST respond with valid JSON in this exact format:
```json
{
    "plan_summary": "Brief description of the overall plan",
    "phases": [
        {
            "phase_name": "Phase name",
            "description": "What this phase accomplishes",
            "is_checkpoint": false,
            "subtasks": [
                {
                    "id": "unique_id",
                    "title": "Task title",
                    "description": "Detailed description of what to do",
                    "assigned_to": "agent_role_name",
                    "depends_on": [],
                    "parallel_group": "group_name_if_parallel"
                }
            ]
        }
    ]
}
```

Only use these agent role names: developer, market_researcher, competitive_analyst, marketing, prevalidation, lead_gen
"""

REVIEW_PROMPT = """You are the Orchestrator reviewing the work of your agent team.

## Your Task
Review the outputs from your agents and:
1. Check for quality, completeness, and accuracy
2. Identify gaps or contradictions between agent outputs
3. Suggest improvements or additional work needed
4. Compile a cohesive summary for the user
5. Decide if we need another round of work or if we're done

## Agent Results
{agent_results}

## Original Task
{original_task}

## Instructions
Provide a comprehensive review with:
1. **Overall Assessment**: How well did the team perform?
2. **Key Findings**: Most important insights across all agents
3. **Gaps & Issues**: What's missing or needs fixing?
4. **Recommendations**: Next steps and improvements
5. **Final Deliverable**: Compiled output ready for the user
"""


class OrchestratorAgent:
    """The Orchestrator agent that manages all other agents."""

    role = AgentRole.ORCHESTRATOR
    name = "Orchestrator"
    description = "Manages all agents, decomposes tasks, coordinates execution, and compiles results."

    def __init__(self) -> None:
        self.llm = get_llm_for_agent(self.role.value)

    async def create_plan(self, task: str, context: dict[str, Any] | None = None) -> TaskPlan:
        """Decompose a task into a structured plan with sub-tasks."""
        messages = [
            SystemMessage(content=PLANNING_PROMPT),
            HumanMessage(content=f"## Task\n{task}"),
        ]

        if context:
            context_str = json.dumps(context, indent=2)
            messages.append(
                HumanMessage(content=f"## Additional Context\n{context_str}")
            )

        response = await self.llm.ainvoke(messages)
        content = response.content if isinstance(response, AIMessage) else str(response)

        # Parse the JSON response
        plan = self._parse_plan(content, task)
        return plan

    def _parse_plan(self, response: str, original_task: str) -> TaskPlan:
        """Parse the orchestrator's planning response into a TaskPlan."""
        task_id = str(uuid.uuid4())[:8]

        # Extract JSON from response
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]

        try:
            plan_data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            # Fallback: create a basic plan
            return TaskPlan(
                task_id=task_id,
                original_task=original_task,
                subtasks=[
                    SubTask(
                        id="research_1",
                        title="Market Research",
                        description=f"Research the market for: {original_task}",
                        assigned_to=AgentRole.MARKET_RESEARCHER,
                    ),
                    SubTask(
                        id="competitive_1",
                        title="Competitive Analysis",
                        description=f"Analyze competitors for: {original_task}",
                        assigned_to=AgentRole.COMPETITIVE_ANALYST,
                    ),
                    SubTask(
                        id="validate_1",
                        title="Pre-validation",
                        description=f"Validate the idea: {original_task}",
                        assigned_to=AgentRole.PREVALIDATION,
                        depends_on=["research_1", "competitive_1"],
                    ),
                ],
                checkpoints=["After research phase", "After validation"],
                current_phase="planning",
            )

        # Build subtasks from phases
        subtasks: list[SubTask] = []
        checkpoints: list[str] = []

        for phase in plan_data.get("phases", []):
            if phase.get("is_checkpoint"):
                checkpoints.append(phase.get("phase_name", "Checkpoint"))

            for st in phase.get("subtasks", []):
                role_str = st.get("assigned_to", "market_researcher")
                try:
                    agent_role = AgentRole(role_str)
                except ValueError:
                    agent_role = AgentRole.MARKET_RESEARCHER

                subtasks.append(
                    SubTask(
                        id=st.get("id", str(uuid.uuid4())[:8]),
                        title=st.get("title", "Untitled"),
                        description=st.get("description", ""),
                        assigned_to=agent_role,
                        depends_on=st.get("depends_on", []),
                    )
                )

        return TaskPlan(
            task_id=task_id,
            original_task=original_task,
            subtasks=subtasks,
            checkpoints=checkpoints,
            current_phase="planned",
        )

    async def review_results(
        self, original_task: str, agent_results: dict[str, str]
    ) -> str:
        """Review all agent outputs and compile a final deliverable."""
        results_str = "\n\n".join(
            f"### {role.upper()}\n{result}" for role, result in agent_results.items()
        )

        prompt = REVIEW_PROMPT.format(
            agent_results=results_str,
            original_task=original_task,
        )

        messages = [
            SystemMessage(content="You are the Orchestrator reviewing your team's work."),
            HumanMessage(content=prompt),
        ]

        response = await self.llm.ainvoke(messages)
        return response.content if isinstance(response, AIMessage) else str(response)

    async def decide_handoff(
        self, subtask_result: str, subtask: SubTask, plan: TaskPlan
    ) -> list[dict[str, str]]:
        """Decide if a subtask result should trigger handoffs to other agents."""
        messages = [
            SystemMessage(
                content=(
                    "You are the Orchestrator. Based on this agent's output, "
                    "decide if any other agents need to be notified or given additional tasks. "
                    "Respond with a JSON array of handoff objects: "
                    '[{"target_agent": "role", "context": "what to pass"}] '
                    "or an empty array [] if no handoffs needed."
                )
            ),
            HumanMessage(
                content=(
                    f"## Completed Subtask\n"
                    f"Agent: {subtask.assigned_to.value}\n"
                    f"Task: {subtask.title}\n\n"
                    f"## Result\n{subtask_result[:3000]}\n\n"
                    f"## Remaining Tasks\n"
                    + "\n".join(
                        f"- {st.title} ({st.assigned_to.value}): {st.status.value}"
                        for st in plan.subtasks
                        if st.status == TaskStatus.PENDING
                    )
                ),
            ),
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content if isinstance(response, AIMessage) else str(response)

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, IndexError):
            return []

    def get_info(self) -> dict[str, Any]:
        """Return agent info."""
        return {
            "role": self.role.value,
            "name": self.name,
            "description": self.description,
            "model": self.llm.__class__.__name__,
            "tools": [],
            "has_skills": False,
        }
