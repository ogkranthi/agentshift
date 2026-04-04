"""Tests for agentshift.compliance — EU AI Act compliance checker."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agentshift.compliance import (
    ComplianceCheck,
    check_eu_ai_act,
    compliance_score,
    render_compliance_report,
    run_compliance,
)
from agentshift.ir import (
    AgentIR,
    Constraints,
    KnowledgeSource,
    Persona,
)

VENV_PYTHON = str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python")
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-agent",
        description="A test agent for compliance testing",
        persona=Persona(system_prompt="You are a helpful assistant."),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


def _compliant_ir() -> AgentIR:
    """An IR that should score highly on EU AI Act checks."""
    return AgentIR(
        name="compliant-agent",
        description="A fully compliant AI assistant that helps users with scheduling tasks",
        persona=Persona(
            system_prompt=(
                "I am an AI assistant. I help users schedule meetings. "
                "If a request involves sensitive decisions, escalate to a human manager. "
                "Always consult a human before making financial commitments."
            ),
        ),
        knowledge=[
            KnowledgeSource(name="calendar-api", kind="url", path="https://api.example.com"),
        ],
        constraints=Constraints(
            guardrails=[
                "Always escalate to human for financial decisions",
                "Do not access personal health data",
                "Human approval required for deletions",
            ],
        ),
    )


def _bare_ir() -> AgentIR:
    """An IR with minimal content — should score poorly."""
    return AgentIR(
        name="bare",
        description="x",
        persona=Persona(system_prompt="Do stuff."),
    )


# ---------------------------------------------------------------------------
# EU AI Act checks — structure
# ---------------------------------------------------------------------------


class TestEuAiActChecks:
    def test_returns_five_checks(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        assert len(checks) == 5

    def test_all_checks_are_compliance_check(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        for c in checks:
            assert isinstance(c, ComplianceCheck)

    def test_articles_present(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        articles = {c.article for c in checks}
        assert articles == {"Art. 13", "Art. 14", "Art. 9", "Art. 10", "Art. 52"}

    def test_status_values_valid(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        for c in checks:
            assert c.status in ("pass", "warn", "fail")


# ---------------------------------------------------------------------------
# EU AI Act — Article 13: Transparency
# ---------------------------------------------------------------------------


class TestArticle13:
    def test_good_description_passes(self):
        ir = _minimal_ir(
            description="A comprehensive agent that manages calendar events and scheduling"
        )
        checks = check_eu_ai_act(ir)
        art13 = next(c for c in checks if c.article == "Art. 13")
        assert art13.status == "pass"

    def test_no_description_fails(self):
        ir = _minimal_ir(description="")
        checks = check_eu_ai_act(ir)
        art13 = next(c for c in checks if c.article == "Art. 13")
        assert art13.status == "fail"

    def test_short_description_fails(self):
        ir = _minimal_ir(description="short")
        checks = check_eu_ai_act(ir)
        art13 = next(c for c in checks if c.article == "Art. 13")
        assert art13.status == "fail"


# ---------------------------------------------------------------------------
# EU AI Act — Article 14: Human oversight
# ---------------------------------------------------------------------------


class TestArticle14:
    def test_oversight_keyword_in_guardrails(self):
        ir = _minimal_ir(constraints=Constraints(guardrails=["Escalate to human for approvals"]))
        checks = check_eu_ai_act(ir)
        art14 = next(c for c in checks if c.article == "Art. 14")
        assert art14.status == "pass"

    def test_oversight_keyword_in_prompt(self):
        ir = _minimal_ir(
            persona=Persona(system_prompt="Always consult a human before making decisions.")
        )
        checks = check_eu_ai_act(ir)
        art14 = next(c for c in checks if c.article == "Art. 14")
        assert art14.status == "pass"

    def test_no_oversight_warns(self):
        ir = _minimal_ir(persona=Persona(system_prompt="Just do tasks."))
        checks = check_eu_ai_act(ir)
        art14 = next(c for c in checks if c.article == "Art. 14")
        assert art14.status == "warn"


# ---------------------------------------------------------------------------
# EU AI Act — Article 9: Risk management
# ---------------------------------------------------------------------------


class TestArticle9:
    def test_guardrails_present_passes(self):
        ir = _minimal_ir(constraints=Constraints(guardrails=["no-diagnose", "no-financial-advice"]))
        checks = check_eu_ai_act(ir)
        art9 = next(c for c in checks if c.article == "Art. 9")
        assert art9.status == "pass"

    def test_no_guardrails_warns(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        art9 = next(c for c in checks if c.article == "Art. 9")
        assert art9.status == "warn"


# ---------------------------------------------------------------------------
# EU AI Act — Article 10: Data governance
# ---------------------------------------------------------------------------


class TestArticle10:
    def test_knowledge_documented_passes(self):
        ir = _minimal_ir(knowledge=[KnowledgeSource(name="docs", kind="file", path="/docs")])
        checks = check_eu_ai_act(ir)
        art10 = next(c for c in checks if c.article == "Art. 10")
        assert art10.status == "pass"

    def test_no_knowledge_warns(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        art10 = next(c for c in checks if c.article == "Art. 10")
        assert art10.status == "warn"


# ---------------------------------------------------------------------------
# EU AI Act — Article 52: AI disclosure
# ---------------------------------------------------------------------------


class TestArticle52:
    def test_ai_disclosure_in_prompt_passes(self):
        ir = _minimal_ir(persona=Persona(system_prompt="I am an AI assistant. I help with tasks."))
        checks = check_eu_ai_act(ir)
        art52 = next(c for c in checks if c.article == "Art. 52")
        assert art52.status == "pass"

    def test_no_disclosure_warns(self):
        ir = _minimal_ir(persona=Persona(system_prompt="I help with tasks."))
        checks = check_eu_ai_act(ir)
        art52 = next(c for c in checks if c.article == "Art. 52")
        assert art52.status == "warn"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestComplianceScore:
    def test_score_range(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        score = compliance_score(checks)
        assert 0 <= score <= 100

    def test_all_pass_is_100(self):
        checks = [
            ComplianceCheck(article="A", requirement="R", status="pass", evidence="e")
            for _ in range(5)
        ]
        assert compliance_score(checks) == 100

    def test_all_fail_is_0(self):
        checks = [
            ComplianceCheck(article="A", requirement="R", status="fail", evidence="e")
            for _ in range(5)
        ]
        assert compliance_score(checks) == 0

    def test_empty_checks_is_0(self):
        assert compliance_score([]) == 0

    def test_compliant_agent_scores_higher(self):
        compliant = _compliant_ir()
        bare = _bare_ir()
        score_c = compliance_score(check_eu_ai_act(compliant))
        score_b = compliance_score(check_eu_ai_act(bare))
        assert score_c > score_b

    def test_compliant_agent_high_score(self):
        ir = _compliant_ir()
        checks = check_eu_ai_act(ir)
        score = compliance_score(checks)
        assert score >= 80


# ---------------------------------------------------------------------------
# run_compliance dispatcher
# ---------------------------------------------------------------------------


class TestRunCompliance:
    def test_eu_ai_act_framework(self):
        ir = _minimal_ir()
        checks = run_compliance(ir, "eu-ai-act")
        assert len(checks) == 5

    def test_unknown_framework_raises(self):
        ir = _minimal_ir()
        with pytest.raises(ValueError, match="Unknown compliance framework"):
            run_compliance(ir, "nonexistent")


# ---------------------------------------------------------------------------
# Rendering — smoke test
# ---------------------------------------------------------------------------


class TestRendering:
    def test_render_does_not_crash(self):
        ir = _minimal_ir()
        checks = check_eu_ai_act(ir)
        # Should not raise
        render_compliance_report(ir, "eu-ai-act", checks)


# ---------------------------------------------------------------------------
# CLI subprocess tests
# ---------------------------------------------------------------------------


class TestComplianceCLI:
    @pytest.fixture
    def simple_skill(self):
        return FIXTURE_DIR / "simple-skill"

    @pytest.fixture
    def pregnancy_companion(self):
        return FIXTURE_DIR / "pregnancy-companion"

    def test_cli_exits_0(self, simple_skill):
        if not simple_skill.exists():
            pytest.skip("simple-skill fixture not found")
        result = subprocess.run(
            [
                VENV_PYTHON,
                "-m",
                "agentshift",
                "compliance",
                str(simple_skill),
                "--from",
                "openclaw",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_cli_json_produces_valid_json(self, simple_skill):
        if not simple_skill.exists():
            pytest.skip("simple-skill fixture not found")
        result = subprocess.run(
            [
                VENV_PYTHON,
                "-m",
                "agentshift",
                "compliance",
                str(simple_skill),
                "--from",
                "openclaw",
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "score" in data
        assert "checks" in data
        assert 0 <= data["score"] <= 100

    def test_cli_json_has_framework(self, simple_skill):
        if not simple_skill.exists():
            pytest.skip("simple-skill fixture not found")
        result = subprocess.run(
            [
                VENV_PYTHON,
                "-m",
                "agentshift",
                "compliance",
                str(simple_skill),
                "--from",
                "openclaw",
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["framework"] == "eu-ai-act"

    def test_pregnancy_companion_scores_high(self, pregnancy_companion):
        """pregnancy-companion has guardrails — should score relatively well."""
        if not pregnancy_companion.exists():
            pytest.skip("pregnancy-companion fixture not found")
        result = subprocess.run(
            [
                VENV_PYTHON,
                "-m",
                "agentshift",
                "compliance",
                str(pregnancy_companion),
                "--from",
                "openclaw",
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        # Should have a decent score due to guardrails and description
        assert data["score"] >= 40
