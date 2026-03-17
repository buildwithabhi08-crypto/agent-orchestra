"""Graph state management for the orchestration workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any

from typing_extensions import TypedDict

from app.models.schemas import StreamEvent, TaskPlan


class OrchestraState(TypedDict):
    """State for the orchestration workflow graph."""

    # The original user task
    task: str

    # Additional context from the user
    context: dict[str, Any]

    # The execution plan created by the orchestrator
    plan: TaskPlan | None

    # Results from each agent, keyed by subtask ID
    agent_results: Annotated[dict[str, str], operator.ior]

    # Messages/events for streaming to the UI
    events: Annotated[list[StreamEvent], operator.add]

    # Current phase of execution
    current_phase: str

    # Whether we're waiting for user approval
    awaiting_approval: bool

    # User approval response
    approval_response: dict[str, Any] | None

    # The final compiled output
    final_output: str

    # Error tracking
    errors: Annotated[list[str], operator.add]

    # Handoff context passed between agents
    handoff_context: dict[str, Any]
