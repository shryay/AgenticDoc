"""Planner Agent — LLM-powered task decomposition.

Receives a raw user request and produces a structured execution plan
with document type, assumptions, and an ordered task list.
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.groq_client import LLMClient
from app.models.schemas import TaskItem, TaskStatus
from app.prompts import PLANNER_SYSTEM, PLANNER_USER

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Breaks down a natural language request into a structured task list."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def plan(self, request: str) -> dict[str, Any]:
        """Generate an execution plan from the user's request.

        Returns:
            Dict with keys: document_type, assumptions, tasks (list[TaskItem]).
        """
        logger.info("Planning started for request: %s", request[:80])

        user_prompt = PLANNER_USER.format(request=request)
        raw_plan = self._llm.generate_json(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.4,
        )

        # Parse into structured TaskItems
        tasks = [
            TaskItem(
                id=task.get("id", idx + 1),
                description=task.get("description", "Unknown task"),
                status=TaskStatus.PENDING,
            )
            for idx, task in enumerate(raw_plan.get("tasks", []))
        ]

        plan_result = {
            "document_type": raw_plan.get("document_type", "Business Document"),
            "assumptions": raw_plan.get("assumptions", []),
            "tasks": tasks,
        }

        logger.info(
            "Plan created: type='%s', tasks=%d, assumptions=%d",
            plan_result["document_type"],
            len(tasks),
            len(plan_result["assumptions"]),
        )
        return plan_result
