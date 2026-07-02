"""Reflector Agent — self-check and quality validation.

Reviews the generated document against the original request and task plan.
Returns a structured quality report indicating whether the document is
approved or needs specific improvements.

This is the mandatory "Engineering Improvement" — Reflection / Self-Check.
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.groq_client import LLMClient
from app.models.schemas import (
    DocumentSection,
    ReflectionReport,
    TaskItem,
)
from app.prompts import (
    IMPROVEMENT_SYSTEM,
    IMPROVEMENT_USER,
    REFLECTOR_SYSTEM,
    REFLECTOR_USER,
)

logger = logging.getLogger(__name__)


class ReflectorAgent:
    """Reviews generated content and optionally triggers improvements."""

    def __init__(self, llm: LLMClient, max_retries: int = 2) -> None:
        self._llm = llm
        self._max_retries = max_retries

    def reflect(
        self,
        request: str,
        document_type: str,
        assumptions: list[str],
        tasks: list[TaskItem],
        sections: list[DocumentSection],
    ) -> ReflectionReport:
        """Review the generated document and return a quality report.

        Args:
            request: Original user request.
            document_type: Determined document type.
            assumptions: Assumptions made during planning.
            tasks: The executed task plan.
            sections: Generated document sections.

        Returns:
            ReflectionReport with approval status, score, and feedback.
        """
        logger.info("Reflection started — reviewing %d sections.", len(sections))

        plan_summary = "\n".join(f"  {t.id}. {t.description}" for t in tasks)
        assumptions_text = "\n".join(f"  - {a}" for a in assumptions) or "None"
        sections_text = self._format_sections(sections)

        user_prompt = REFLECTOR_USER.format(
            request=request,
            document_type=document_type,
            plan_summary=plan_summary,
            assumptions=assumptions_text,
            sections_text=sections_text,
        )

        raw_report = self._llm.generate_json(
            system_prompt=REFLECTOR_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.3,
        )

        report = ReflectionReport(
            approved=raw_report.get("approved", True),
            quality_score=max(1, min(10, raw_report.get("quality_score", 7))),
            issues=raw_report.get("issues", []),
            suggestions=raw_report.get("suggestions", []),
        )

        logger.info(
            "Reflection complete: approved=%s, score=%d, issues=%d",
            report.approved,
            report.quality_score,
            len(report.issues),
        )
        return report

    def improve_sections(
        self,
        request: str,
        sections: list[DocumentSection],
        report: ReflectionReport,
    ) -> list[DocumentSection]:
        """Attempt to improve sections based on reflection feedback.

        Iterates through sections and rewrites any that may address the
        reported issues. Limited to `_max_retries` improvement cycles.
        """
        if report.approved or not report.issues:
            return sections

        logger.info("Improving sections based on %d issues.", len(report.issues))

        improved = list(sections)
        issues_text = "\n".join(f"  - {i}" for i in report.issues)
        suggestions_text = "\n".join(f"  - {s}" for s in report.suggestions)

        # Improve the last few sections (most likely to be incomplete)
        for idx in range(max(0, len(improved) - 3), len(improved)):
            section = improved[idx]
            try:
                user_prompt = IMPROVEMENT_USER.format(
                    request=request,
                    heading=section.heading,
                    content=section.content,
                    issues=issues_text,
                    suggestions=suggestions_text,
                )

                raw = self._llm.generate_json(
                    system_prompt=IMPROVEMENT_SYSTEM,
                    user_prompt=user_prompt,
                    temperature=0.6,
                )

                improved[idx] = DocumentSection(
                    heading=raw.get("heading", section.heading),
                    content=raw.get("content", section.content),
                    level=raw.get("level", section.level),
                    bullet_points=raw.get("bullet_points", section.bullet_points),
                    table_data=raw.get("table_data", section.table_data),
                )
                logger.info("Improved section '%s'.", improved[idx].heading)

            except Exception as exc:
                logger.warning("Failed to improve section '%s': %s", section.heading, exc)

        return improved

    @staticmethod
    def _format_sections(sections: list[DocumentSection]) -> str:
        """Format sections into a readable text block for the reviewer."""
        parts = []
        for s in sections:
            part = f"## {s.heading}\n{s.content}"
            if s.bullet_points:
                part += "\n" + "\n".join(f"  • {bp}" for bp in s.bullet_points)
            if s.table_data:
                for row in s.table_data:
                    part += "\n  | " + " | ".join(row) + " |"
            parts.append(part)
        return "\n\n".join(parts)
