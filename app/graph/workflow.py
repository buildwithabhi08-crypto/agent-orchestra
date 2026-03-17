"""Main LangGraph workflow for the multi-agent orchestration system."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.agents.competitive_analyst import CompetitiveAnalystAgent
from app.agents.developer import DeveloperAgent
from app.agents.lead_gen import LeadGenAgent
from app.agents.market_researcher import MarketResearcherAgent
from app.agents.marketing import MarketingAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.prevalidation import PrevalidationAgent
from app.graph.state import OrchestraState
from app.models.schemas import AgentRole, StreamEvent, TaskStatus


def _event(event_type: str, agent: str = "", content: str = "", **kwargs: Any) -> StreamEvent:
    """Create a stream event."""
    return StreamEvent(
        event_type=event_type,
        agent=agent,
        content=content,
        metadata=kwargs,
        timestamp=datetime.utcnow(),
    )


# --- Graph Nodes ---


async def plan_task(state: OrchestraState) -> dict[str, Any]:
    """Orchestrator decomposes the task into a plan."""
    orchestrator = OrchestratorAgent()

    events = [_event("phase_start", "orchestrator", "Planning task decomposition...")]

    try:
        plan = await orchestrator.create_plan(state["task"], state.get("context"))
        events.append(
            _event(
                "plan_created",
                "orchestrator",
                f"Created plan with {len(plan.subtasks)} subtasks across "
                f"{len(set(st.assigned_to for st in plan.subtasks))} agents.",
                subtask_count=len(plan.subtasks),
                checkpoints=plan.checkpoints,
            )
        )
        return {
            "plan": plan,
            "current_phase": "planned",
            "events": events,
        }
    except Exception as e:
        return {
            "events": events + [_event("error", "orchestrator", f"Planning failed: {str(e)}")],
            "errors": [f"Planning error: {str(e)}"],
            "current_phase": "failed",
        }


async def execute_research_phase(state: OrchestraState) -> dict[str, Any]:
    """Execute research-phase subtasks in parallel (market research + competitive analysis)."""
    plan = state["plan"]
    if not plan:
        return {"errors": ["No plan available"], "current_phase": "failed"}

    events = [_event("phase_start", "orchestrator", "Starting research phase...")]
    results: dict[str, str] = {}

    # Find research-phase subtasks (no dependencies)
    research_tasks = [
        st for st in plan.subtasks
        if not st.depends_on and st.assigned_to in (
            AgentRole.MARKET_RESEARCHER,
            AgentRole.COMPETITIVE_ANALYST,
        )
    ]

    if not research_tasks:
        # Find any tasks without dependencies
        research_tasks = [st for st in plan.subtasks if not st.depends_on]

    # Execute in parallel
    agent_map = _get_agent_map()

    async def run_subtask(subtask: Any) -> tuple[str, str]:
        agent_cls = agent_map.get(subtask.assigned_to)
        if not agent_cls:
            return subtask.id, f"Error: No agent for role {subtask.assigned_to}"

        agent = agent_cls()
        events.append(
            _event("agent_start", subtask.assigned_to.value, f"Working on: {subtask.title}")
        )

        try:
            context = state.get("handoff_context", {})
            result = await agent.invoke(subtask.description, context)
            subtask.status = TaskStatus.COMPLETED
            subtask.result = result
            events.append(
                _event("agent_complete", subtask.assigned_to.value, f"Completed: {subtask.title}")
            )
            return subtask.id, result
        except Exception as e:
            subtask.status = TaskStatus.FAILED
            error_msg = f"Error: {str(e)}"
            subtask.result = error_msg
            events.append(
                _event("agent_error", subtask.assigned_to.value, error_msg)
            )
            return subtask.id, error_msg

    # Run all research tasks in parallel
    parallel_results = await asyncio.gather(
        *[run_subtask(st) for st in research_tasks],
        return_exceptions=True,
    )

    for item in parallel_results:
        if isinstance(item, Exception):
            results[f"error_{id(item)}"] = str(item)
        else:
            task_id, result = item
            results[task_id] = result

    events.append(_event("phase_complete", "orchestrator", "Research phase complete."))

    return {
        "agent_results": results,
        "events": events,
        "current_phase": "research_complete",
        "plan": plan,
    }


async def checkpoint_research(state: OrchestraState) -> dict[str, Any]:
    """Checkpoint after research phase - request user approval."""
    events = [
        _event(
            "checkpoint",
            "orchestrator",
            "Research phase complete. Awaiting your approval to proceed.",
            phase="research",
            results_summary={
                k: v[:500] for k, v in state.get("agent_results", {}).items()
            },
        )
    ]

    # Use LangGraph interrupt for human-in-the-loop
    approval = interrupt(
        {
            "type": "approval_request",
            "phase": "research",
            "message": "Research phase is complete. Review the results and approve to continue.",
            "results": {k: v[:1000] for k, v in state.get("agent_results", {}).items()},
        }
    )

    approved = approval.get("approved", True) if isinstance(approval, dict) else True
    feedback = approval.get("feedback", "") if isinstance(approval, dict) else ""

    if not approved:
        events.append(_event("checkpoint_rejected", "orchestrator", f"Feedback: {feedback}"))

    return {
        "events": events,
        "awaiting_approval": False,
        "approval_response": {"approved": approved, "feedback": feedback},
        "current_phase": "research_approved" if approved else "research_revision",
    }


async def execute_validation_phase(state: OrchestraState) -> dict[str, Any]:
    """Execute validation subtasks using research results as context."""
    plan = state["plan"]
    if not plan:
        return {"errors": ["No plan available"], "current_phase": "failed"}

    events = [_event("phase_start", "orchestrator", "Starting validation phase...")]
    results: dict[str, str] = {}

    # Find validation subtasks
    validation_tasks = [
        st for st in plan.subtasks
        if st.assigned_to == AgentRole.PREVALIDATION and st.status == TaskStatus.PENDING
    ]

    if not validation_tasks:
        # Check for any remaining pending tasks that depend on completed ones
        completed_ids = {st.id for st in plan.subtasks if st.status == TaskStatus.COMPLETED}
        validation_tasks = [
            st for st in plan.subtasks
            if st.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in st.depends_on)
            and st.assigned_to not in (AgentRole.DEVELOPER, AgentRole.MARKETING, AgentRole.LEAD_GEN)
        ]

    # Build context from previous results
    context = dict(state.get("handoff_context", {}))
    for task_id, result in state.get("agent_results", {}).items():
        context[f"previous_result_{task_id}"] = result[:2000]

    # Add approval feedback if any
    approval = state.get("approval_response")
    if approval and approval.get("feedback"):
        context["user_feedback"] = approval["feedback"]

    agent_map = _get_agent_map()

    for subtask in validation_tasks:
        agent_cls = agent_map.get(subtask.assigned_to)
        if not agent_cls:
            continue

        agent = agent_cls()
        events.append(
            _event("agent_start", subtask.assigned_to.value, f"Working on: {subtask.title}")
        )

        try:
            result = await agent.invoke(subtask.description, context)
            subtask.status = TaskStatus.COMPLETED
            subtask.result = result
            results[subtask.id] = result
            events.append(
                _event("agent_complete", subtask.assigned_to.value, f"Completed: {subtask.title}")
            )
        except Exception as e:
            subtask.status = TaskStatus.FAILED
            error_msg = f"Error: {str(e)}"
            subtask.result = error_msg
            results[subtask.id] = error_msg
            events.append(_event("agent_error", subtask.assigned_to.value, error_msg))

    events.append(_event("phase_complete", "orchestrator", "Validation phase complete."))

    return {
        "agent_results": results,
        "events": events,
        "current_phase": "validation_complete",
        "plan": plan,
    }


async def checkpoint_validation(state: OrchestraState) -> dict[str, Any]:
    """Checkpoint after validation - request user approval before building."""
    events = [
        _event(
            "checkpoint",
            "orchestrator",
            "Validation complete. Approve to proceed with development and marketing.",
            phase="validation",
        )
    ]

    approval = interrupt(
        {
            "type": "approval_request",
            "phase": "validation",
            "message": "Validation phase is complete. Review and approve to proceed with building and marketing.",
            "results": {k: v[:1000] for k, v in state.get("agent_results", {}).items()},
        }
    )

    approved = approval.get("approved", True) if isinstance(approval, dict) else True
    feedback = approval.get("feedback", "") if isinstance(approval, dict) else ""

    return {
        "events": events,
        "awaiting_approval": False,
        "approval_response": {"approved": approved, "feedback": feedback},
        "current_phase": "validation_approved" if approved else "validation_revision",
    }


async def execute_build_and_market_phase(state: OrchestraState) -> dict[str, Any]:
    """Execute development and marketing subtasks in parallel."""
    plan = state["plan"]
    if not plan:
        return {"errors": ["No plan available"], "current_phase": "failed"}

    events = [_event("phase_start", "orchestrator", "Starting build & marketing phase...")]
    results: dict[str, str] = {}

    # Find remaining subtasks
    remaining_tasks = [st for st in plan.subtasks if st.status == TaskStatus.PENDING]

    # Build context from all previous results
    context = dict(state.get("handoff_context", {}))
    for task_id, result in state.get("agent_results", {}).items():
        context[f"previous_result_{task_id}"] = result[:2000]

    approval = state.get("approval_response")
    if approval and approval.get("feedback"):
        context["user_feedback"] = approval["feedback"]

    agent_map = _get_agent_map()

    async def run_subtask(subtask: Any) -> tuple[str, str]:
        agent_cls = agent_map.get(subtask.assigned_to)
        if not agent_cls:
            return subtask.id, f"Error: No agent for role {subtask.assigned_to}"

        agent = agent_cls()
        events.append(
            _event("agent_start", subtask.assigned_to.value, f"Working on: {subtask.title}")
        )

        try:
            result = await agent.invoke(subtask.description, context)
            subtask.status = TaskStatus.COMPLETED
            subtask.result = result
            events.append(
                _event("agent_complete", subtask.assigned_to.value, f"Completed: {subtask.title}")
            )
            return subtask.id, result
        except Exception as e:
            subtask.status = TaskStatus.FAILED
            error_msg = f"Error: {str(e)}"
            subtask.result = error_msg
            events.append(_event("agent_error", subtask.assigned_to.value, error_msg))
            return subtask.id, error_msg

    # Run remaining tasks in parallel
    if remaining_tasks:
        parallel_results = await asyncio.gather(
            *[run_subtask(st) for st in remaining_tasks],
            return_exceptions=True,
        )

        for item in parallel_results:
            if isinstance(item, Exception):
                results[f"error_{id(item)}"] = str(item)
            else:
                task_id, result = item
                results[task_id] = result

    events.append(_event("phase_complete", "orchestrator", "Build & marketing phase complete."))

    return {
        "agent_results": results,
        "events": events,
        "current_phase": "build_complete",
        "plan": plan,
    }


async def compile_results(state: OrchestraState) -> dict[str, Any]:
    """Orchestrator reviews all results and compiles the final output."""
    events = [_event("phase_start", "orchestrator", "Compiling final results...")]

    orchestrator = OrchestratorAgent()

    try:
        final_output = await orchestrator.review_results(
            state["task"],
            state.get("agent_results", {}),
        )
        events.append(_event("task_complete", "orchestrator", "All work complete!"))

        return {
            "final_output": final_output,
            "events": events,
            "current_phase": "completed",
        }
    except Exception as e:
        return {
            "final_output": "Error compiling results. Raw results are available.",
            "events": events + [_event("error", "orchestrator", str(e))],
            "errors": [f"Compilation error: {str(e)}"],
            "current_phase": "completed_with_errors",
        }


# --- Routing Functions ---


def route_after_research_checkpoint(state: OrchestraState) -> str:
    """Route based on research checkpoint approval."""
    phase = state.get("current_phase", "")
    if phase == "research_approved":
        return "execute_validation"
    elif phase == "research_revision":
        return "execute_research"
    return "execute_validation"


def route_after_validation_checkpoint(state: OrchestraState) -> str:
    """Route based on validation checkpoint approval."""
    phase = state.get("current_phase", "")
    if phase == "validation_approved":
        return "execute_build_and_market"
    elif phase == "validation_revision":
        return "execute_validation"
    return "execute_build_and_market"


# --- Agent Map ---


def _get_agent_map() -> dict[AgentRole, type]:
    """Get mapping of agent roles to agent classes."""
    return {
        AgentRole.MARKET_RESEARCHER: MarketResearcherAgent,
        AgentRole.COMPETITIVE_ANALYST: CompetitiveAnalystAgent,
        AgentRole.PREVALIDATION: PrevalidationAgent,
        AgentRole.DEVELOPER: DeveloperAgent,
        AgentRole.MARKETING: MarketingAgent,
        AgentRole.LEAD_GEN: LeadGenAgent,
    }


# --- Build Graph ---


def build_workflow() -> StateGraph:
    """Build the LangGraph workflow for agent orchestration."""
    workflow = StateGraph(OrchestraState)

    # Add nodes
    workflow.add_node("plan_task", plan_task)
    workflow.add_node("execute_research", execute_research_phase)
    workflow.add_node("checkpoint_research", checkpoint_research)
    workflow.add_node("execute_validation", execute_validation_phase)
    workflow.add_node("checkpoint_validation", checkpoint_validation)
    workflow.add_node("execute_build_and_market", execute_build_and_market_phase)
    workflow.add_node("compile_results", compile_results)

    # Set entry point
    workflow.set_entry_point("plan_task")

    # Add edges
    workflow.add_edge("plan_task", "execute_research")
    workflow.add_edge("execute_research", "checkpoint_research")

    # Conditional routing after research checkpoint
    workflow.add_conditional_edges(
        "checkpoint_research",
        route_after_research_checkpoint,
        {
            "execute_validation": "execute_validation",
            "execute_research": "execute_research",
        },
    )

    workflow.add_edge("execute_validation", "checkpoint_validation")

    # Conditional routing after validation checkpoint
    workflow.add_conditional_edges(
        "checkpoint_validation",
        route_after_validation_checkpoint,
        {
            "execute_build_and_market": "execute_build_and_market",
            "execute_validation": "execute_validation",
        },
    )

    workflow.add_edge("execute_build_and_market", "compile_results")
    workflow.add_edge("compile_results", END)

    return workflow


def create_graph():
    """Create and compile the workflow graph."""
    from langgraph.checkpoint.memory import MemorySaver

    workflow = build_workflow()
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
