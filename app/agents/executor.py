"""Executor Agent — executes each planned task to generate document sections.

Iterates through the task plan, calling the LLM for each task to produce
structured document content. Uses mock research data for realistic output.
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.groq_client import LLMClient
from app.models.schemas import DocumentSection, TaskItem, TaskStatus
from app.prompts import EXECUTOR_SYSTEM, EXECUTOR_USER
from app.tools.research_tool import ResearchTool

logger = logging.getLogger(__name__)


class ExecutorAgent:
    """Runs through the task list sequentially to generate document sections."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self._research = ResearchTool()

    def execute(
        self,
        request: str,
        document_type: str,
        assumptions: list[str],
        tasks: list[TaskItem],
    ) -> list[DocumentSection]:
        """Execute all tasks and return ordered document sections.

        Args:
            request: Original user request.
            document_type: Type of document being generated.
            assumptions: List of assumptions made by the planner.
            tasks: Ordered list of tasks to execute.

        Returns:
            List of DocumentSection objects, one per task.
        """
        sections: list[DocumentSection] = []

        plan_summary = "\n".join(
            f"  {t.id}. {t.description}" for t in tasks
        )
        assumptions_text = "\n".join(f"  - {a}" for a in assumptions) or "None"

        for task in tasks:
            task.status = TaskStatus.IN_PROGRESS
            logger.info("Executing task #%d: %s", task.id, task.description)

            try:
                section = self._execute_single_task(
                    request=request,
                    document_type=document_type,
                    plan_summary=plan_summary,
                    assumptions=assumptions_text,
                    task=task,
                    previous_sections=sections,
                )
                sections.append(section)
                task.status = TaskStatus.COMPLETED
                task.result = f"Generated section: {section.heading}"
                logger.info("Task #%d completed: %s", task.id, section.heading)

            except Exception as exc:
                task.status = TaskStatus.FAILED
                task.result = f"Failed: {exc}"
                logger.error("Task #%d failed: %s", task.id, exc)
                # Create a fallback section so the document isn't incomplete
                sections.append(
                    DocumentSection(
                        heading=f"Section {task.id}",
                        content=f"This section could not be generated. Task: {task.description}",
                        level=1,
                    )
                )

        return sections

    def _execute_single_task(
        self,
        request: str,
        document_type: str,
        plan_summary: str,
        assumptions: str,
        task: TaskItem,
        previous_sections: list[DocumentSection],
    ) -> DocumentSection:
        """Execute a single task by calling the LLM with full context."""
        # Build context from previously generated sections
        previous_context = self._build_context(previous_sections)

        user_prompt = EXECUTOR_USER.format(
            request=request,
            document_type=document_type,
            plan_summary=plan_summary,
            assumptions=assumptions,
            task_id=task.id,
            task_description=task.description,
            previous_context=previous_context,
        )

        raw_section = self._llm.generate_json(
            system_prompt=EXECUTOR_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.7,
        )

        return DocumentSection(
            heading=raw_section.get("heading", f"Section {task.id}"),
            content=raw_section.get("content", ""),
            level=raw_section.get("level", 1),
            bullet_points=raw_section.get("bullet_points", []),
            table_data=raw_section.get("table_data"),
        )

    @staticmethod
    def _build_context(sections: list[DocumentSection]) -> str:
        """Summarize previously generated sections for continuity."""
        if not sections:
            return "No previous sections yet — this is the first section."

        lines = []
        for s in sections:
            lines.append(f"[{s.heading}]: {s.content[:150]}...")
        return "\n".join(lines)
