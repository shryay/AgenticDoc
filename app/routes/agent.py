"""Agent API routes — thin controller layer.

Handles HTTP concerns (validation, status codes, file serving) and
delegates all business logic to AgentService.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import AgentRequest, AgentResponse
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent"])

# Single service instance (stateless, safe to share)
_agent_service = AgentService()


@router.post(
    "/agent",
    response_model=AgentResponse,
    summary="Process a natural language request",
    description=(
        "Accepts a user request, autonomously plans tasks, generates content, "
        "performs self-check, and produces a polished Word document.\n\n"
        "**Pipeline:** Request Validation → Planning → Execution → Reflection → Document Generation"
    ),
    responses={
        200: {"description": "Successfully generated document with full execution trace"},
        400: {"description": "Invalid request — too short, too long, or not document-related"},
        503: {"description": "LLM service unavailable — all retries exhausted"},
        500: {"description": "Unexpected server error"},
    },
)
def process_agent_request(body: AgentRequest) -> AgentResponse:
    """POST /agent — main entry point for the autonomous agent."""
    logger.info("Received request: %s", body.request[:80])

    try:
        response = _agent_service.process_request(body.request)
        return response

    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    except RuntimeError as exc:
        logger.error("Agent pipeline failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Agent processing failed: {exc}. Please try again.",
        )

    except Exception as exc:
        logger.exception("Unexpected error in agent pipeline")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Check server logs for details.",
        )


@router.get(
    "/download/{filename}",
    summary="Download a generated document",
    description="Serves the generated .docx file for download by filename.",
    responses={
        200: {"description": "Document file download"},
        404: {"description": "Document not found"},
        400: {"description": "Invalid file type requested"},
    },
)
def download_document(filename: str) -> FileResponse:
    """GET /download/{filename} — serve a generated .docx file."""
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    filepath = Path("output") / filename

    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Document '{filename}' not found. Check the document_path in the agent response.",
        )

    if filepath.suffix != ".docx":
        raise HTTPException(status_code=400, detail="Only .docx files can be downloaded.")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
