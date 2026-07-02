"""FastAPI application entry point.

Configures the app, registers routes, sets up logging and CORS,
and validates that the Groq API key is available on startup.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.agent import router as agent_router


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration on startup."""
    settings = get_settings()

    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        logger.error(
            "GROQ_API_KEY is not set! "
            "Copy .env.example to .env and add your key from https://console.groq.com/keys"
        )
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  Autonomous AI Agent — Ready")
    logger.info("  Model: %s", settings.groq_model)
    logger.info("  Fallback: %s", settings.groq_fallback_model)
    logger.info("  Output dir: %s", settings.output_dir)
    logger.info("=" * 60)

    yield  # Application runs

    logger.info("Agent shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Autonomous AI Agent",
    description=(
        "An autonomous AI agent that understands natural language requests, "
        "creates its own task plan, executes each step with LLM-powered reasoning, "
        "performs self-reflection for quality assurance, and produces polished "
        "Microsoft Word (.docx) documents."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for local development / demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(agent_router)


@app.get("/", tags=["Health"])
def health_check():
    """Root endpoint — simple health check."""
    return {
        "status": "healthy",
        "service": "Autonomous AI Agent",
        "version": "1.0.0",
        "endpoints": {
            "POST /agent": "Submit a natural language request",
            "GET /download/{filename}": "Download generated document",
            "GET /docs": "Interactive API documentation",
        },
    }
