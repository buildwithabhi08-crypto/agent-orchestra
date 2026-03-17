"""Pydantic models for the application."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    DEVELOPER = "developer"
    MARKET_RESEARCHER = "market_researcher"
    COMPETITIVE_ANALYST = "competitive_analyst"
    MARKETING = "marketing"
    PREVALIDATION = "prevalidation"
    LEAD_GEN = "lead_gen"


class SubTask(BaseModel):
    id: str
    title: str
    description: str
    assigned_to: AgentRole
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskPlan(BaseModel):
    task_id: str
    original_task: str
    subtasks: list[SubTask] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    current_phase: str = "planning"


class TaskRequest(BaseModel):
    description: str
    context: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    plan: TaskPlan | None = None
    results: dict[str, Any] = Field(default_factory=dict)
    messages: list[dict[str, str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalRequest(BaseModel):
    approved: bool
    feedback: str = ""


class AgentMessage(BaseModel):
    role: AgentRole
    content: str
    target: AgentRole | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamEvent(BaseModel):
    event_type: str
    agent: str = ""
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
