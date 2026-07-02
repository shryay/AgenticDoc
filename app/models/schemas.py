"""Pydantic models for request/response validation and internal data transfer.

Strict boundary models — request DTOs validate input, response DTOs shape output.
Internal models (TaskItem, DocumentSection) transfer data between agents.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Status of an individual task in the execution plan."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Request DTO (API boundary — inbound)
# ---------------------------------------------------------------------------

class AgentRequest(BaseModel):
    """Incoming user request — validated at the API boundary.

    Guardrails:
    - Must be 10-2000 characters
    - Must contain at least 3 words
    - Must contain document-related intent (not random gibberish)
    - Stripped of excess whitespace
    """

    request: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural language request describing the document to generate.",
        examples=[
            "Create a project proposal for developing a mobile banking app.",
            "Prepare meeting minutes for the Q3 engineering review.",
        ],
    )

    @field_validator("request")
    @classmethod
    def validate_request_quality(cls, value: str) -> str:
        """Ensure the request is meaningful and actionable."""
        stripped = value.strip()

        # Collapse multiple whitespace into single spaces
        stripped = re.sub(r"\s+", " ", stripped)

        # Must have enough words to be actionable
        words = stripped.split()
        if len(words) < 3:
            raise ValueError(
                "Request must contain at least 3 words to be actionable. "
                "Example: 'Create a project proposal for an AI system.'"
            )

        # Must not be all numbers or special characters
        alpha_chars = sum(1 for c in stripped if c.isalpha())
        if alpha_chars < len(stripped) * 0.3:
            raise ValueError(
                "Request must contain meaningful text, not just numbers or symbols."
            )

        # Check for document-related intent keywords
        intent_keywords = {
            "create", "generate", "prepare", "write", "draft", "make",
            "build", "design", "develop", "plan", "document", "report",
            "proposal", "meeting", "minutes", "review", "summary", "brief",
            "memo", "specification", "sop", "procedure", "analysis",
            "assessment", "strategy", "roadmap", "budget", "project",
            "business", "technical", "executive", "quarterly", "annual",
            "need", "want", "require", "help", "client", "company",
        }
        request_words_lower = {w.lower().strip(".,!?;:") for w in words}
        if not request_words_lower & intent_keywords:
            raise ValueError(
                "Request doesn't appear to be a document generation request. "
                "Please describe what kind of document you need. "
                "Examples: proposal, report, meeting minutes, project plan."
            )

        return stripped


# ---------------------------------------------------------------------------
# Internal data models (passed between agents)
# ---------------------------------------------------------------------------

class TaskItem(BaseModel):
    """A single task in the agent's execution plan."""

    id: int
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None


class DocumentSection(BaseModel):
    """A single section of the generated document."""

    heading: str
    content: str
    level: int = Field(default=1, ge=1, le=3)
    bullet_points: list[str] = Field(default_factory=list)
    table_data: Optional[list[list[str]]] = None


class ReflectionReport(BaseModel):
    """Output of the Reflection / Self-Check step."""

    approved: bool
    quality_score: int = Field(..., ge=1, le=10)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution log entry (tracks what the agent did step-by-step)
# ---------------------------------------------------------------------------

class ExecutionLogEntry(BaseModel):
    """A single step in the agent's execution log — shows autonomous decision-making."""

    step: int
    agent: str  # Which agent performed this step
    action: str  # What the agent did
    result: str  # Outcome of the action
    duration_seconds: float  # How long this step took
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Response DTO (API boundary — outbound)
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    """Final response returned to the caller.

    Includes the full task plan, assumptions, reflection report,
    step-by-step execution log, and the path to the generated document.
    """

    request: str
    document_type: str
    task_plan: list[TaskItem]
    assumptions: list[str] = Field(default_factory=list)
    execution_log: list[ExecutionLogEntry] = Field(default_factory=list)
    reflection: ReflectionReport
    document_path: str
    summary: str
    execution_time_seconds: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
