"""Tests for agentshift.diff — portability matrix."""

from __future__ import annotations

from agentshift.diff import (
    FULL,
    NONE,
    PARTIAL,
    PLATFORM_SUPPORT,
    STUB,
    compute_diff,
    render_diff_table,
)
from agentshift.ir import (
    AgentIR,
    Constraints,
    KnowledgeSource,
    Persona,
    Tool,
    Trigger,
    TriggerDelivery,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-agent",
        description="A test agent",
        persona=Persona(system_prompt="Do things."),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


def _shell_tool(name: str = "git") -> Tool:
    return Tool(name=name, description="shell binary", kind="shell")


def _mcp_tool(name: str = "slack") -> Tool:
    return Tool(name=name, description="mcp server", kind="mcp")


def _cron_trigger(delivery_channel: str | None = None) -> Trigger:
    delivery = TriggerDelivery(channel=delivery_channel) if delivery_channel else None
    return Trigger(kind="cron", cron_expr="0 9 * * *", delivery=delivery)


# ---------------------------------------------------------------------------
# compute_diff — structure
# ---------------------------------------------------------------------------


class TestComputeDiffStructure:
    def test_returns_all_targets(self):
        ir = _minimal_ir()
        targets = ["claude-code", "copilot"]
        result = compute_diff(ir, targets)
        assert set(result["scores"].keys()) == set(targets)

    def test_scores_in_range(self):
        ir = _minimal_ir(
            tools=[_shell_tool(), _mcp_tool()],
            knowledge=[KnowledgeSource(name="k", kind="file", path="/k")],
        )
        result = compute_diff(ir, list(PLATFORM_SUPPORT.keys()))
        for target, score in result["scores"].items():
            assert 0 <= score <= 100, f"{target} score {score} out of range"

    def test_active_components_only(self):
        ir = _minimal_ir()  # instructions only, no tools/knowledge/triggers
        result = compute_diff(ir, ["claude-code"])
        assert result["active"] == ["instructions"]

    def test_no_triggers_no_trigger_components(self):
        ir = _minimal_ir(tools=[_shell_tool()])
        result = compute_diff(ir, ["claude-code", "copilot"])
        assert "triggers_cron" not in result["active"]
        assert "triggers_delivery" not in result["active"]

    def test_cron_trigger_in_active(self):
        ir = _minimal_ir(triggers=[_cron_trigger()])
        result = compute_diff(ir, ["claude-code"])
        assert "triggers_cron" in result["active"]

    def test_delivery_trigger_in_active(self):
        ir = _minimal_ir(triggers=[_cron_trigger(delivery_channel="telegram")])
        result = compute_diff(ir, ["claude-code"])
        assert "triggers_delivery" in result["active"]

    def test_mcp_tool_in_active(self):
        ir = _minimal_ir(tools=[_mcp_tool()])
        result = compute_diff(ir, ["claude-code"])
        assert "tools_mcp" in result["active"]

    def test_knowledge_in_active(self):
        ir = _minimal_ir(knowledge=[KnowledgeSource(name="k", kind="file", path="/p")])
        result = compute_diff(ir, ["claude-code"])
        assert "knowledge" in result["active"]

    def test_constraints_in_active(self):
        ir = _minimal_ir(constraints=Constraints(supported_os=["darwin"]))
        result = compute_diff(ir, ["claude-code"])
        assert "constraints" in result["active"]

    def test_constraints_not_in_active_when_empty(self):
        ir = _minimal_ir()
        result = compute_diff(ir, ["claude-code"])
        assert "constraints" not in result["active"]


# ---------------------------------------------------------------------------
# compute_diff — fidelity values
# ---------------------------------------------------------------------------


class TestFidelityValues:
    def test_claude_code_instructions_full(self):
        ir = _minimal_ir()
        result = compute_diff(ir, ["claude-code"])
        fidelity, _, _ = result["components"]["instructions"]["claude-code"]
        assert fidelity == FULL

    def test_copilot_triggers_cron_none(self):
        ir = _minimal_ir(triggers=[_cron_trigger()])
        result = compute_diff(ir, ["copilot"])
        fidelity, _, _ = result["components"]["triggers_cron"]["copilot"]
        assert fidelity == NONE

    def test_claude_code_triggers_cron_partial(self):
        ir = _minimal_ir(triggers=[_cron_trigger()])
        result = compute_diff(ir, ["claude-code"])
        fidelity, _, _ = result["components"]["triggers_cron"]["claude-code"]
        assert fidelity == PARTIAL

    def test_copilot_mcp_partial(self):
        ir = _minimal_ir(tools=[_mcp_tool()])
        result = compute_diff(ir, ["copilot"])
        fidelity, _, _ = result["components"]["tools_mcp"]["copilot"]
        assert fidelity == PARTIAL

    def test_bedrock_shell_none(self):
        ir = _minimal_ir(tools=[_shell_tool()])
        result = compute_diff(ir, ["bedrock"])
        fidelity, _, _ = result["components"]["tools_shell"]["bedrock"]
        assert fidelity == NONE

    def test_bedrock_constraints_stub(self):
        ir = _minimal_ir(constraints=Constraints(supported_os=["linux"]))
        result = compute_diff(ir, ["bedrock"])
        fidelity, _, _ = result["components"]["constraints"]["bedrock"]
        assert fidelity == STUB


# ---------------------------------------------------------------------------
# compute_diff — scores
# ---------------------------------------------------------------------------


class TestScores:
    def test_instructions_only_claude_code_perfect(self):
        """Instructions-only agent on claude-code should score 100."""
        ir = _minimal_ir()
        result = compute_diff(ir, ["claude-code"])
        assert result["scores"]["claude-code"] == 100.0

    def test_copilot_lower_than_claude_for_cron_agent(self):
        """An agent with cron should score lower on copilot than claude-code."""
        ir = _minimal_ir(triggers=[_cron_trigger()])
        result = compute_diff(ir, ["claude-code", "copilot"])
        assert result["scores"]["claude-code"] > result["scores"]["copilot"]

    def test_score_zero_impossible_for_supported_platform(self):
        """Even the worst case shouldn't hit 0 because instructions always get weight."""
        ir = _minimal_ir(
            tools=[_shell_tool(), _mcp_tool()],
            knowledge=[KnowledgeSource(name="k", kind="file", path="/k")],
            triggers=[_cron_trigger(delivery_channel="telegram")],
            constraints=Constraints(supported_os=["linux"]),
        )
        result = compute_diff(ir, ["bedrock"])
        # bedrock drops shell + delivery — but instructions are partial (60)
        assert result["scores"]["bedrock"] > 0

    def test_empty_agent_no_system_prompt_no_components(self):
        """Agent with nothing active scores 100 (nothing to lose)."""
        ir = AgentIR(name="empty", description="empty", persona=Persona())
        result = compute_diff(ir, ["claude-code"])
        assert result["scores"]["claude-code"] == 100.0


# ---------------------------------------------------------------------------
# render_diff_table — smoke test (no crash, no exception)
# ---------------------------------------------------------------------------


class TestRenderDiffTable:
    def test_renders_without_error(self, capsys):
        ir = _minimal_ir(
            tools=[_shell_tool(), _mcp_tool()],
            triggers=[_cron_trigger(delivery_channel="telegram")],
        )
        # Should not raise
        render_diff_table(ir, ["claude-code", "copilot"])

    def test_unknown_target_skipped(self, capsys):
        ir = _minimal_ir()
        # Should not raise, just warn
        render_diff_table(ir, ["claude-code", "nonexistent-platform"])

    def test_all_unknown_targets_exits_gracefully(self, capsys):
        ir = _minimal_ir()
        render_diff_table(ir, ["nonexistent"])
