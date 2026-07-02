"""Agent service — orchestration layer.

Coordinates the full Planner → Executor → Reflector pipeline.
This is the single entry point that the API route calls.
No business logic here — just sequencing, data mapping, and execution tracking.
"""

from __future__ import annotations

import logging
import re
import time

from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.reflector import ReflectorAgent
from app.config import get_settings
from app.llm.groq_client import LLMClient
from app.models.schemas import AgentResponse, ExecutionLogEntry, TaskItem
from app.tools.document_tool import DocumentTool

logger = logging.getLogger(__name__)


class AgentService:
    """Orchestrates the autonomous agent pipeline end-to-end."""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = LLMClient()
        self._planner = PlannerAgent(self._llm)
        self._executor = ExecutorAgent(self._llm)
        self._reflector = ReflectorAgent(
            self._llm, max_retries=settings.max_reflection_retries
        )
        self._doc_tool = DocumentTool(output_dir=settings.output_dir)

    def process_request(self, request: str) -> AgentResponse:
        """Run the full agent pipeline on a user request.

        Flow:
            1. Plan — decompose request into tasks + assumptions
            2. Execute — generate document sections for each task
            3. Reflect — self-check quality; improve if needed
            4. Generate — produce the final .docx file

        Args:
            request: Natural language user request.

        Returns:
            AgentResponse with task plan, execution log, reflection, and document path.
        """
        pipeline_start = time.time()
        execution_log: list[ExecutionLogEntry] = []
        step_counter = 0

        logger.info("=" * 60)
        logger.info("AGENT PIPELINE STARTED")
        logger.info("Request: %s", request[:100])
        logger.info("=" * 60)

        # --- plan phase ---
        step_counter += 1
        step_start = time.time()
        logger.info("planning...")

        plan = self._planner.plan(request)
        document_type = plan["document_type"]
        assumptions = plan["assumptions"]
        tasks: list[TaskItem] = plan["tasks"]

        execution_log.append(ExecutionLogEntry(
            step=step_counter,
            agent="PlannerAgent",
            action=f"Analyzed request and decomposed into {len(tasks)} tasks",
            result=(
                f"Document type: '{document_type}'. "
                f"Tasks: {', '.join(t.description[:50] for t in tasks)}. "
                f"Assumptions: {len(assumptions)} made."
            ),
            duration_seconds=round(time.time() - step_start, 2),
        ))

        logger.info(
            "Plan ready: type='%s', %d tasks, %d assumptions",
            document_type, len(tasks), len(assumptions),
        )

        # --- execution phase ---
        step_counter += 1
        step_start = time.time()
        logger.info("executing tasks...")

        sections = self._executor.execute(
            request=request,
            document_type=document_type,
            assumptions=assumptions,
            tasks=tasks,
        )

        completed = sum(1 for t in tasks if t.status.value == "completed")
        failed = sum(1 for t in tasks if t.status.value == "failed")
        execution_log.append(ExecutionLogEntry(
            step=step_counter,
            agent="ExecutorAgent",
            action=f"Executed {len(tasks)} tasks to generate document sections",
            result=(
                f"Generated {len(sections)} sections. "
                f"{completed} tasks completed, {failed} failed. "
                f"Sections: {', '.join(s.heading for s in sections)}."
            ),
            duration_seconds=round(time.time() - step_start, 2),
        ))

        logger.info("Execution complete: %d sections generated.", len(sections))

        # --- reflection / self-correction loop ---
        step_counter += 1
        step_start = time.time()
        logger.info("evaluating quality...")

        reflection = self._reflector.reflect(
            request=request,
            document_type=document_type,
            assumptions=assumptions,
            tasks=tasks,
            sections=sections,
        )

        reflection_action = (
            f"Reviewed document quality — score: {reflection.quality_score}/10"
        )
        reflection_result = (
            f"{'APPROVED' if reflection.approved else 'NEEDS IMPROVEMENT'}. "
            f"Issues: {reflection.issues if reflection.issues else 'None'}. "
            f"Suggestions: {reflection.suggestions if reflection.suggestions else 'None'}."
        )

        # trigger targeted rewrite if quality isn't met
        if not reflection.approved:
            logger.info(
                "Reflection flagged %d issues (score: %d). Improving...",
                len(reflection.issues), reflection.quality_score,
            )
            sections = self._reflector.improve_sections(
                request=request,
                sections=sections,
                report=reflection,
            )
            
            # evaluate again post-improvement
            reflection = self._reflector.reflect(
                request=request,
                document_type=document_type,
                assumptions=assumptions,
                tasks=tasks,
                sections=sections,
            )
            reflection_action += " → triggered improvements → re-reviewed"
            reflection_result = (
                f"Post-improvement: {'APPROVED' if reflection.approved else 'PARTIAL'}. "
                f"Final score: {reflection.quality_score}/10."
            )
            logger.info(
                "Post-improvement reflection: approved=%s, score=%d",
                reflection.approved, reflection.quality_score,
            )

        execution_log.append(ExecutionLogEntry(
            step=step_counter,
            agent="ReflectorAgent",
            action=reflection_action,
            result=reflection_result,
            duration_seconds=round(time.time() - step_start, 2),
        ))

        # --- document compilation ---
        step_counter += 1
        step_start = time.time()
        logger.info("writing to docx...")

        title = self._derive_title(request, document_type)
        doc_path = self._doc_tool.generate(
            title=title,
            document_type=document_type,
            sections=sections,
            assumptions=assumptions,
        )

        execution_log.append(ExecutionLogEntry(
            step=step_counter,
            agent="DocumentTool",
            action="Generated polished Word document (.docx)",
            result=f"Document saved to: {doc_path}",
            duration_seconds=round(time.time() - step_start, 2),
        ))

        # ── Assemble Response ─────────────────────────────────────
        total_time = round(time.time() - pipeline_start, 2)

        summary = (
            f"Successfully generated a '{document_type}' with {len(sections)} sections "
            f"in {total_time}s. Quality score: {reflection.quality_score}/10. "
            f"{'Document approved by reflection agent.' if reflection.approved else 'Document generated with partial improvements.'}"
        )

        logger.info("AGENT PIPELINE COMPLETED in %.2fs", total_time)
        logger.info(summary)

        return AgentResponse(
            request=request,
            document_type=document_type,
            task_plan=tasks,
            assumptions=assumptions,
            execution_log=execution_log,
            reflection=reflection,
            document_path=doc_path,
            summary=summary,
            execution_time_seconds=total_time,
        )

    @staticmethod
    def _derive_title(request: str, document_type: str) -> str:
        """Extract a clean title from the request or use the document type."""
        patterns = [
            r"(?:create|generate|prepare|write|draft)\s+(?:a\s+)?(.+?)(?:\.|$)",
            r"(?:for|about)\s+(.+?)(?:\.|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, request.lower())
            if match:
                title = match.group(1).strip().title()
                if len(title) > 10:
                    return title

        return document_type
