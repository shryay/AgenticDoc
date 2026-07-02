# 🤖 AgenticDoc — Autonomous Document Synthesis Engine

An autonomous AI agent built with **FastAPI + Groq (Llama 3.3 70B) + python-docx** that accepts natural language requests, creates its own execution plan, generates professional content, performs self-reflection for quality assurance, and produces polished Microsoft Word (.docx) documents.

**No LangChain. No frameworks. Pure engineering.**

---

## Architecture

```
POST /agent  →  Request Validator (Pydantic + guardrails)
                        │
                        ▼
                 Planner Agent ─── LLM ──→ Task List + Assumptions
                        │
                        ▼
                 Executor Agent ─── LLM ──→ Document Sections (per task)
                        │
                        ▼
                 Reflector Agent ─── LLM ──→ Quality Score + Issues
                        │
                   ┌────┴─────┐
                   │          │
              Score ≥ 7   Score < 7
                   │          │
                   │    Improve Sections
                   │          │
                   │    Re-reflect
                   │          │
                   └────┬─────┘
                        │
                        ▼
                 Document Tool ──→ Professional .docx
                        │
                        ▼
                 JSON Response (plan + log + reflection + file path)
```

---

## 🔧 Core Feature: Reflection / Self-Check

> **What:** After the Executor generates all sections, a Reflector Agent reviews the complete output against the original request using a structured evaluation rubric.
>
> **Why:** Without reflection, the agent is fire-and-forget — it generates once and hopes for the best. With reflection, the agent catches missing sections, inconsistencies, and quality gaps *autonomously*, then triggers targeted improvements.
>
> **How:** The Reflector scores the document on 5 criteria (completeness, coherence, professionalism, structure, accuracy). If the score is below 7/10, it identifies specific issues, triggers re-generation of flagged sections, then re-evaluates. This dramatically improves output quality.

### Additional Engineering Highlights

While Reflection is the primary feature, the system also demonstrates:

- **Multi-step Planning** — The Planner Agent autonomously creates its own TODO list
- **Retry & Fallback** — Exponential backoff with automatic model downgrade (70B → 8B) on rate limits
- **Request Validation & Guardrails** — Intent detection, gibberish rejection, length/word-count checks
- **Error Handling & Recovery** — Failed tasks produce fallback sections; the document is always generated

---

## Quick Start

### 1. Install
```bash
# Clone the repository
git clone https://github.com/shryay/AgenticDoc.git
cd AgenticDoc

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env → add your Groq API key from https://console.groq.com/keys
```

### 3. Run
```bash
uvicorn app.main:app --reload
```

### 4. Test
Open **http://localhost:8000/docs** for interactive Swagger UI, or use curl:

#### Test 1 — Standard Business Request
```bash
curl -X POST http://localhost:8000/agent ^
  -H "Content-Type: application/json" ^
  -d "{\"request\": \"Create a business proposal for introducing AI chatbot support in a retail company. Include executive summary, objectives, implementation timeline, budget estimate, and risk assessment.\"}"
```

#### Test 2 — Complex / Ambiguous Request
```bash
curl -X POST http://localhost:8000/agent ^
  -H "Content-Type: application/json" ^
  -d "{\"request\": \"Our client wants an AI-based customer support system. Budget is not finalized. Timeline is unclear. Some stakeholders prefer chatbot, others prefer live agents. Prepare a project proposal and make reasonable assumptions wherever information is missing.\"}"
```

---

## Project Structure

```
AgenticDoc/
├── app/
│   ├── main.py                 # FastAPI app, CORS, startup validation
│   ├── config.py               # Pydantic Settings from .env
│   ├── prompts.py              # All LLM prompts (centralized, auditable)
│   ├── routes/
│   │   └── agent.py            # POST /agent, GET /download/{filename}
│   ├── models/
│   │   └── schemas.py          # Pydantic DTOs (request, response, internal)
│   ├── services/
│   │   └── agent_service.py    # Pipeline orchestration + execution logging
│   ├── agents/
│   │   ├── planner.py          # LLM-powered task decomposition
│   │   ├── executor.py         # Section-by-section content generation
│   │   └── reflector.py        # Quality self-check & section improvement
│   ├── tools/
│   │   ├── document_tool.py    # python-docx generation (styled output)
│   │   └── research_tool.py    # Mock data provider
│   └── llm/
│       └── groq_client.py      # Groq wrapper with retry & model fallback
├── output/                      # Generated .docx files
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## API Response Structure

```json
{
  "request": "Original user request",
  "document_type": "Project Proposal",
  "task_plan": [
    {"id": 1, "description": "Analyze objectives", "status": "completed", "result": "..."},
    {"id": 2, "description": "Generate executive summary", "status": "completed", "result": "..."}
  ],
  "assumptions": [
    "Budget assumed at $75,000-$150,000 for medium-scale project",
    "Timeline assumed at 16-20 weeks"
  ],
  "execution_log": [
    {"step": 1, "agent": "PlannerAgent", "action": "Analyzed request...", "duration_seconds": 1.23},
    {"step": 2, "agent": "ExecutorAgent", "action": "Executed 6 tasks...", "duration_seconds": 8.45},
    {"step": 3, "agent": "ReflectorAgent", "action": "Reviewed quality...", "duration_seconds": 1.87},
    {"step": 4, "agent": "DocumentTool", "action": "Generated .docx", "duration_seconds": 0.05}
  ],
  "reflection": {
    "approved": true,
    "quality_score": 8,
    "issues": [],
    "suggestions": ["Consider adding a competitive analysis section"]
  },
  "document_path": "output/Business_Proposal_20260703.docx",
  "execution_time_seconds": 11.6
}
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **API** | FastAPI | Async, auto-docs, Pydantic-native |
| **LLM** | Groq (Llama 3.3 70B) | Free tier, ultra-fast LPU inference (~10x faster than GPU) |
| **Document** | python-docx | Full formatting control, no Word installation needed |
| **Validation** | Pydantic v2 | Type-safe DTOs with custom validators at every boundary |
| **Config** | pydantic-settings | Typed env config with .env file support |

---

## Tradeoff: Single-Agent Pipeline vs Multi-Agent Framework

I intentionally chose a single-agent pipeline (Planner → Executor → Reflector) over a multi-agent framework like CrewAI or LangGraph because:

1. **Debuggability** — Each stage is a simple function call with clear inputs/outputs. No message-passing complexity.
2. **Transparency** — The execution log shows exactly what happened at each step and how long it took.
3. **Extensibility** — Adding a new agent stage is just adding a new class and one call in the orchestrator.
4. **Speed** — No framework overhead. Raw Groq API calls complete in seconds.

The architecture still demonstrates autonomous planning, decision-making, and self-correction — which is what matters.
