"""Mock research tool — provides contextually relevant synthetic data.

Returns realistic business data based on the document type, giving the LLM
concrete numbers and details to weave into the generated content.
"""

from __future__ import annotations


class ResearchTool:
    """Provides mock research data based on document type and topic."""

    # Pre-built data pools keyed by document category
    _DATA_POOLS: dict[str, dict] = {
        "proposal": {
            "budget_ranges": {
                "small": "$25,000 – $50,000",
                "medium": "$75,000 – $150,000",
                "large": "$200,000 – $500,000",
            },
            "timeline_phases": [
                "Discovery & Requirements (2-3 weeks)",
                "Design & Architecture (3-4 weeks)",
                "Development Sprint 1 (4 weeks)",
                "Development Sprint 2 (4 weeks)",
                "Testing & QA (2-3 weeks)",
                "Deployment & Launch (1-2 weeks)",
            ],
            "team_structure": [
                "Project Manager (1)",
                "Lead Developer (1)",
                "Full-Stack Developers (2-3)",
                "UI/UX Designer (1)",
                "QA Engineer (1)",
            ],
            "risk_categories": [
                "Technical complexity",
                "Scope creep",
                "Resource availability",
                "Third-party dependencies",
                "Regulatory compliance",
            ],
        },
        "report": {
            "kpis": {
                "Revenue Growth": "+12.5% QoQ",
                "Customer Acquisition": "2,340 new customers",
                "Churn Rate": "3.2% (down from 4.1%)",
                "NPS Score": "72 (industry avg: 45)",
                "Operating Margin": "18.3%",
            },
            "departments": [
                "Engineering",
                "Sales & Marketing",
                "Product",
                "Human Resources",
                "Finance",
            ],
        },
        "meeting_minutes": {
            "attendees": [
                "Sarah Chen (VP Engineering)",
                "Michael Rodriguez (Product Lead)",
                "Priya Sharma (Design Director)",
                "James Wilson (CTO)",
                "Emily Park (Project Manager)",
            ],
            "action_items_template": [
                "Review and finalize requirements document",
                "Schedule follow-up with stakeholders",
                "Prepare cost-benefit analysis",
                "Update project timeline in JIRA",
                "Share meeting notes with wider team",
            ],
        },
        "sop": {
            "compliance_frameworks": [
                "ISO 27001",
                "SOC 2 Type II",
                "GDPR",
                "HIPAA",
            ],
            "review_cycle": "Quarterly review with annual full audit",
        },
        "default": {
            "company_name": "Acme Technologies Inc.",
            "industry": "Technology / SaaS",
            "team_size": "50-200 employees",
            "fiscal_year": "FY 2025-26",
        },
    }

    def gather(self, document_type: str) -> dict:
        """Return mock data relevant to the document type.

        Args:
            document_type: The type of document being generated.

        Returns:
            Dict of contextually relevant mock data.
        """
        doc_lower = document_type.lower()

        # Match document type to the best data pool
        if any(kw in doc_lower for kw in ("proposal", "plan", "spec")):
            pool_key = "proposal"
        elif any(kw in doc_lower for kw in ("report", "review", "quarterly")):
            pool_key = "report"
        elif any(kw in doc_lower for kw in ("meeting", "minutes")):
            pool_key = "meeting_minutes"
        elif any(kw in doc_lower for kw in ("sop", "procedure", "standard")):
            pool_key = "sop"
        else:
            pool_key = "default"

        # Merge category-specific data with defaults
        result = dict(self._DATA_POOLS["default"])
        result.update(self._DATA_POOLS[pool_key])
        return result
