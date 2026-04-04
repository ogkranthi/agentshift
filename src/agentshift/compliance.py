"""AgentShift compliance — EU AI Act and future regulatory framework checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rich import box
from rich.console import Console
from rich.table import Table

from agentshift.ir import AgentIR

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ComplianceCheck:
    """A single compliance check result."""

    article: str
    requirement: str
    status: Literal["pass", "warn", "fail"]
    evidence: str
    recommendation: str | None = None


# ---------------------------------------------------------------------------
# EU AI Act checks
# ---------------------------------------------------------------------------

_HUMAN_OVERSIGHT_KEYWORDS = [
    "human approval",
    "escalate",
    "manager approval",
    "human review",
    "consult",
    "human oversight",
    "human-in-the-loop",
    "manual review",
]

_AI_DISCLOSURE_KEYWORDS = [
    "i am an ai",
    "i'm an ai",
    "ai assistant",
    "language model",
    "not a human",
    "artificial intelligence",
    "ai-powered",
    "automated system",
]


def check_eu_ai_act(ir: AgentIR) -> list[ComplianceCheck]:
    """Run EU AI Act compliance checks against an AgentIR.

    Checks:
        Art. 13 — Transparency (clear description)
        Art. 14 — Human oversight (escalation guardrails)
        Art. 9  — Risk management (safety guardrails)
        Art. 10 — Data governance (knowledge sources documented)
        Art. 52 — AI disclosure (agent identifies as AI)
    """
    checks: list[ComplianceCheck] = []

    # Article 13: Transparency — agent has clear description
    checks.append(
        ComplianceCheck(
            article="Art. 13",
            requirement="Agent has clear description",
            status="pass" if ir.description and len(ir.description) > 20 else "fail",
            evidence=(f"description: {ir.description[:80]}" if ir.description else "missing"),
            recommendation=(
                None
                if ir.description and len(ir.description) > 20
                else "Add a clear description explaining what this agent does"
            ),
        )
    )

    # Article 14: Human oversight — escalation guardrails
    guardrail_texts = ir.constraints.guardrails
    has_oversight = any(
        any(kw in g.lower() for kw in ("human", "escalat", "approv")) for g in guardrail_texts
    )
    prompt_lower = (ir.persona.system_prompt or "").lower()
    has_oversight_in_prompt = any(kw in prompt_lower for kw in _HUMAN_OVERSIGHT_KEYWORDS)
    oversight_found = has_oversight or has_oversight_in_prompt
    checks.append(
        ComplianceCheck(
            article="Art. 14",
            requirement="Human oversight mechanism documented",
            status="pass" if oversight_found else "warn",
            evidence=("found in guardrails or instructions" if oversight_found else "not found"),
            recommendation=(
                None if oversight_found else "Document when the agent should escalate to a human"
            ),
        )
    )

    # Article 9: Risk management — safety guardrails
    checks.append(
        ComplianceCheck(
            article="Art. 9",
            requirement="Safety guardrails documented",
            status="pass" if guardrail_texts else "warn",
            evidence=(f"{len(guardrail_texts)} guardrails" if guardrail_texts else "none"),
            recommendation=(
                None
                if guardrail_texts
                else "Add safety guardrails (e.g., no-diagnose, no-financial-advice)"
            ),
        )
    )

    # Article 10: Data governance — knowledge sources documented
    checks.append(
        ComplianceCheck(
            article="Art. 10",
            requirement="Knowledge sources documented",
            status="pass" if ir.knowledge else "warn",
            evidence=(
                f"{len(ir.knowledge)} sources documented"
                if ir.knowledge
                else "no knowledge sources"
            ),
            recommendation=None,
        )
    )

    # Article 52: AI disclosure — agent discloses AI nature
    has_disclosure = any(kw in prompt_lower for kw in _AI_DISCLOSURE_KEYWORDS)
    checks.append(
        ComplianceCheck(
            article="Art. 52",
            requirement="Agent discloses AI nature",
            status="pass" if has_disclosure else "warn",
            evidence=(
                "disclosure found in system prompt" if has_disclosure else "no AI disclosure found"
            ),
            recommendation=(
                None
                if has_disclosure
                else "Add disclosure: e.g., 'I am an AI assistant and may make mistakes.' in system prompt"
            ),
        )
    )

    return checks


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_STATUS_WEIGHTS = {"pass": 100, "warn": 50, "fail": 0}


def compliance_score(checks: list[ComplianceCheck]) -> int:
    """Compute 0-100 compliance score from a list of checks."""
    if not checks:
        return 0
    return int(sum(_STATUS_WEIGHTS[c.status] for c in checks) / len(checks))


# ---------------------------------------------------------------------------
# Framework dispatcher
# ---------------------------------------------------------------------------

_FRAMEWORKS: dict[str, type] = {
    "eu-ai-act": check_eu_ai_act,  # type: ignore[dict-item]
}


def run_compliance(ir: AgentIR, framework: str = "eu-ai-act") -> list[ComplianceCheck]:
    """Run compliance checks for the given framework."""
    check_fn = _FRAMEWORKS.get(framework)
    if check_fn is None:
        msg = f"Unknown compliance framework: {framework!r}. Supported: {', '.join(_FRAMEWORKS)}"
        raise ValueError(msg)
    return check_fn(ir)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_STATUS_COLOR = {"pass": "green", "warn": "yellow", "fail": "red"}
_STATUS_SYMBOL = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}


def render_compliance_report(ir: AgentIR, framework: str, checks: list[ComplianceCheck]) -> None:
    """Render compliance report to console using rich."""
    console = Console()
    score = compliance_score(checks)

    table = Table(
        title=f"[bold]{ir.name}[/bold] — {framework} Compliance ({score}%)",
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("Article", style="bold")
    table.add_column("Requirement")
    table.add_column("Status", justify="center")
    table.add_column("Evidence")
    table.add_column("Recommendation")

    for check in checks:
        color = _STATUS_COLOR[check.status]
        status_label = f"[{color}]{_STATUS_SYMBOL[check.status]}[/{color}]"
        table.add_row(
            check.article,
            check.requirement,
            status_label,
            check.evidence,
            check.recommendation or "—",
        )

    console.print()
    console.print(table)
    console.print()
