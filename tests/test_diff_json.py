"""Tests for agentshift diff --output-format json."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agentshift.diff import PLATFORM_SUPPORT, _component_display, compute_diff
from agentshift.ir import (
    AgentIR,
    Constraints,
    KnowledgeSource,
    Persona,
    Tool,
    Trigger,
    TriggerDelivery,
)

VENV_PYTHON = str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python")
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


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
# JSON serialization of compute_diff output
# ---------------------------------------------------------------------------


class TestDiffJsonStructure:
    """Test that compute_diff output can be serialized to the expected JSON schema."""

    def _build_json_payload(self, ir: AgentIR, targets: list[str], platform: str = "openclaw"):
        result = compute_diff(ir, targets)
        scores = {t: int(s) for t, s in result["scores"].items()}
        components = []
        for comp in result["active"]:
            row: dict = {"name": _component_display(comp, ir), "source": True}
            for target in targets:
                fidelity, _, _ = result["components"][comp][target]
                row[target] = fidelity
            components.append(row)
        return {
            "agent_name": ir.name,
            "source_platform": ir.metadata.source_platform or platform,
            "targets": targets,
            "scores": scores,
            "components": components,
        }

    def test_json_is_valid(self):
        ir = _minimal_ir(tools=[_shell_tool(), _mcp_tool()])
        payload = self._build_json_payload(ir, ["claude-code", "copilot"])
        # Round-trip through JSON
        serialized = json.dumps(payload)
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)

    def test_agent_name_present(self):
        ir = _minimal_ir(name="my-agent")
        payload = self._build_json_payload(ir, ["claude-code"])
        assert payload["agent_name"] == "my-agent"

    def test_source_platform_present(self):
        ir = _minimal_ir()
        payload = self._build_json_payload(ir, ["claude-code"], platform="openclaw")
        assert payload["source_platform"] == "openclaw"

    def test_targets_list_matches(self):
        targets = ["claude-code", "copilot", "bedrock"]
        ir = _minimal_ir()
        payload = self._build_json_payload(ir, targets)
        assert payload["targets"] == targets

    def test_scores_dict_has_correct_keys(self):
        targets = ["claude-code", "copilot", "bedrock"]
        ir = _minimal_ir()
        payload = self._build_json_payload(ir, targets)
        assert set(payload["scores"].keys()) == set(targets)

    def test_scores_are_integers_0_to_100(self):
        ir = _minimal_ir(
            tools=[_shell_tool(), _mcp_tool()],
            knowledge=[KnowledgeSource(name="k", kind="file", path="/k")],
            triggers=[_cron_trigger(delivery_channel="telegram")],
        )
        payload = self._build_json_payload(ir, list(PLATFORM_SUPPORT.keys()))
        for target, score in payload["scores"].items():
            assert isinstance(score, int), f"{target} score is not int"
            assert 0 <= score <= 100, f"{target} score {score} out of range"

    def test_components_list_present(self):
        ir = _minimal_ir(tools=[_shell_tool()])
        payload = self._build_json_payload(ir, ["claude-code"])
        assert isinstance(payload["components"], list)
        assert len(payload["components"]) > 0

    def test_components_have_name_and_source(self):
        ir = _minimal_ir(tools=[_shell_tool()])
        payload = self._build_json_payload(ir, ["claude-code"])
        for comp in payload["components"]:
            assert "name" in comp
            assert comp["source"] is True

    def test_component_fidelity_values_valid(self):
        ir = _minimal_ir(tools=[_shell_tool(), _mcp_tool()])
        targets = ["claude-code", "bedrock"]
        payload = self._build_json_payload(ir, targets)
        valid = {"full", "partial", "stub", "none"}
        for comp in payload["components"]:
            for t in targets:
                assert comp[t] in valid, f"{comp['name']}[{t}] = {comp[t]} not in {valid}"

    def test_empty_agent_json(self):
        ir = AgentIR(name="empty", description="empty", persona=Persona())
        payload = self._build_json_payload(ir, ["claude-code"])
        assert payload["components"] == []
        assert payload["scores"]["claude-code"] == 100

    def test_full_agent_component_count(self):
        ir = _minimal_ir(
            tools=[_shell_tool(), _mcp_tool()],
            knowledge=[KnowledgeSource(name="k", kind="file", path="/k")],
            triggers=[_cron_trigger(delivery_channel="telegram")],
            constraints=Constraints(supported_os=["darwin"]),
        )
        payload = self._build_json_payload(ir, ["claude-code"])
        # instructions, tools_shell, tools_mcp, knowledge, triggers_cron,
        # triggers_delivery, constraints = 7 components
        assert len(payload["components"]) == 7


# ---------------------------------------------------------------------------
# CLI subprocess tests
# ---------------------------------------------------------------------------


class TestDiffJsonCLI:
    """Test --output-format json via subprocess CLI call."""

    @pytest.fixture
    def simple_skill(self):
        return FIXTURE_DIR / "simple-skill"

    def test_cli_json_returns_valid_json(self, simple_skill):
        if not simple_skill.exists():
            pytest.skip("simple-skill fixture not found")
        result = subprocess.run(
            [
                VENV_PYTHON,
                "-m",
                "agentshift",
                "diff",
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
        assert "agent_name" in data
        assert "scores" in data
        assert "components" in data

    def test_cli_json_scores_are_integers(self, simple_skill):
        if not simple_skill.exists():
            pytest.skip("simple-skill fixture not found")
        result = subprocess.run(
            [
                VENV_PYTHON,
                "-m",
                "agentshift",
                "diff",
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
        for score in data["scores"].values():
            assert isinstance(score, int)

    def test_cli_text_format_default(self, simple_skill):
        """Default format (text) should NOT produce JSON."""
        if not simple_skill.exists():
            pytest.skip("simple-skill fixture not found")
        result = subprocess.run(
            [VENV_PYTHON, "-m", "agentshift", "diff", str(simple_skill), "--from", "openclaw"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        # Should not be valid JSON (it's a rich table)
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.stdout)
