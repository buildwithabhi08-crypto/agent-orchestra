"""FastAPI routes for the Agent Orchestra API."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.agents.competitive_analyst import CompetitiveAnalystAgent
from app.agents.developer import DeveloperAgent
from app.agents.lead_gen import LeadGenAgent
from app.agents.market_researcher import MarketResearcherAgent
from app.agents.marketing import MarketingAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.prevalidation import PrevalidationAgent
from app.graph.workflow import create_graph
from app.models.schemas import (
    ApprovalRequest,
    StreamEvent,
    TaskRequest,
    TaskResponse,
    TaskStatus,
)

router = APIRouter()

# In-memory task storage
tasks: dict[str, dict[str, Any]] = {}
task_events: dict[str, list[StreamEvent]] = {}
task_graphs: dict[str, Any] = {}
task_threads: dict[str, dict[str, Any]] = {}


def _get_all_agents() -> list[dict[str, Any]]:
    """Get info for all agents."""
    agents = [
        OrchestratorAgent(),
        DeveloperAgent(),
        MarketResearcherAgent(),
        CompetitiveAnalystAgent(),
        MarketingAgent(),
        PrevalidationAgent(),
        LeadGenAgent(),
    ]
    return [a.get_info() for a in agents]


@router.get("/agents")
async def list_agents():
    """List all available agents and their configurations."""
    return {"agents": _get_all_agents()}


@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """Submit a new task to the orchestrator for processing."""
    task_id = str(uuid.uuid4())[:8]

    tasks[task_id] = {
        "task_id": task_id,
        "description": request.description,
        "context": request.context,
        "status": TaskStatus.PENDING,
        "results": {},
        "messages": [],
        "created_at": datetime.utcnow(),
        "plan": None,
    }
    task_events[task_id] = []

    # Start processing in background
    asyncio.create_task(_process_task(task_id, request.description, request.context))

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=tasks[task_id]["created_at"],
    )


async def _process_task(task_id: str, description: str, context: dict[str, Any]):
    """Process a task through the orchestration workflow."""
    tasks[task_id]["status"] = TaskStatus.PLANNING

    graph = create_graph()
    task_graphs[task_id] = graph

    thread_config = {"configurable": {"thread_id": task_id}}
    task_threads[task_id] = thread_config

    initial_state = {
        "task": description,
        "context": context,
        "plan": None,
        "agent_results": {},
        "events": [],
        "current_phase": "starting",
        "awaiting_approval": False,
        "approval_response": None,
        "final_output": "",
        "errors": [],
        "handoff_context": context,
    }

    try:
        tasks[task_id]["status"] = TaskStatus.IN_PROGRESS

        async for event in graph.astream(initial_state, config=thread_config):
            # Process events from the graph
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    # Store events
                    new_events = node_output.get("events", [])
                    task_events[task_id].extend(new_events)

                    # Update task data
                    if node_output.get("plan"):
                        tasks[task_id]["plan"] = node_output["plan"]
                    if node_output.get("agent_results"):
                        tasks[task_id]["results"].update(node_output["agent_results"])
                    if node_output.get("final_output"):
                        tasks[task_id]["final_output"] = node_output["final_output"]
                    if node_output.get("current_phase"):
                        tasks[task_id]["current_phase"] = node_output["current_phase"]

                    # Check if awaiting approval (interrupted)
                    if node_output.get("awaiting_approval"):
                        tasks[task_id]["status"] = TaskStatus.AWAITING_APPROVAL

        # Check final state
        phase = tasks[task_id].get("current_phase", "")
        if "complete" in phase:
            tasks[task_id]["status"] = TaskStatus.COMPLETED
        elif "fail" in phase:
            tasks[task_id]["status"] = TaskStatus.FAILED

    except Exception as e:
        error_str = str(e)
        # Check if this is an interrupt (human-in-the-loop)
        if "interrupt" in error_str.lower() or "GraphInterrupt" in error_str:
            tasks[task_id]["status"] = TaskStatus.AWAITING_APPROVAL
            task_events[task_id].append(
                StreamEvent(
                    event_type="checkpoint",
                    agent="orchestrator",
                    content="Awaiting your approval to proceed.",
                    timestamp=datetime.utcnow(),
                )
            )
        else:
            tasks[task_id]["status"] = TaskStatus.FAILED
            task_events[task_id].append(
                StreamEvent(
                    event_type="error",
                    agent="system",
                    content=f"Task failed: {error_str}",
                    timestamp=datetime.utcnow(),
                )
            )


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get the status and results of a task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    events = task_events.get(task_id, [])

    return {
        "task_id": task_id,
        "status": task["status"],
        "current_phase": task.get("current_phase", ""),
        "plan": task.get("plan"),
        "results": task.get("results", {}),
        "final_output": task.get("final_output", ""),
        "events": [
            {
                "event_type": e.event_type,
                "agent": e.agent,
                "content": e.content,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events[-50:]  # Last 50 events
        ],
        "created_at": task["created_at"].isoformat(),
    }


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, approval: ApprovalRequest):
    """Approve or reject a checkpoint to continue task execution."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    if tasks[task_id]["status"] != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail="Task is not awaiting approval")

    graph = task_graphs.get(task_id)
    thread_config = task_threads.get(task_id)

    if not graph or not thread_config:
        raise HTTPException(status_code=400, detail="No active workflow for this task")

    tasks[task_id]["status"] = TaskStatus.IN_PROGRESS
    task_events[task_id].append(
        StreamEvent(
            event_type="approval",
            agent="user",
            content=f"{'Approved' if approval.approved else 'Rejected'}: {approval.feedback}",
            timestamp=datetime.utcnow(),
        )
    )

    # Resume the graph with the approval response
    approval_data = {"approved": approval.approved, "feedback": approval.feedback}

    asyncio.create_task(
        _resume_task(task_id, graph, thread_config, approval_data)
    )

    return {"status": "resumed", "approved": approval.approved}


async def _resume_task(
    task_id: str, graph: Any, thread_config: dict, approval_data: dict
):
    """Resume a task after approval."""
    try:
        async for event in graph.astream(
            graph.update_state(thread_config, approval_data, as_node="__interrupt__"),
            config=thread_config,
        ):
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    new_events = node_output.get("events", [])
                    task_events[task_id].extend(new_events)

                    if node_output.get("agent_results"):
                        tasks[task_id]["results"].update(node_output["agent_results"])
                    if node_output.get("final_output"):
                        tasks[task_id]["final_output"] = node_output["final_output"]
                    if node_output.get("current_phase"):
                        tasks[task_id]["current_phase"] = node_output["current_phase"]

        phase = tasks[task_id].get("current_phase", "")
        if "complete" in phase:
            tasks[task_id]["status"] = TaskStatus.COMPLETED

    except Exception as e:
        error_str = str(e)
        if "interrupt" in error_str.lower() or "GraphInterrupt" in error_str:
            tasks[task_id]["status"] = TaskStatus.AWAITING_APPROVAL
        else:
            tasks[task_id]["status"] = TaskStatus.FAILED
            task_events[task_id].append(
                StreamEvent(
                    event_type="error",
                    agent="system",
                    content=f"Resume failed: {error_str}",
                    timestamp=datetime.utcnow(),
                )
            )


@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """Stream real-time events for a task via Server-Sent Events."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        last_index = 0
        while True:
            events = task_events.get(task_id, [])
            if len(events) > last_index:
                for event in events[last_index:]:
                    yield {
                        "event": event.event_type,
                        "data": json.dumps({
                            "agent": event.agent,
                            "content": event.content,
                            "metadata": event.metadata,
                            "timestamp": event.timestamp.isoformat(),
                        }),
                    }
                last_index = len(events)

            # Check if task is done
            task_status = tasks.get(task_id, {}).get("status")
            if task_status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                yield {
                    "event": "done",
                    "data": json.dumps({"status": task_status}),
                }
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.get("/tasks")
async def list_tasks():
    """List all tasks."""
    return {
        "tasks": [
            {
                "task_id": tid,
                "description": t["description"][:100],
                "status": t["status"],
                "current_phase": t.get("current_phase", ""),
                "created_at": t["created_at"].isoformat(),
            }
            for tid, t in tasks.items()
        ]
    }
