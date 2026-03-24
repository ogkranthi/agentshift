"""Tests for the Vertex AI emitter — IR → agent.json + README.md"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentshift.emitters.vertex import emit
from agentshift.ir import (
    AgentIR,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
    Trigger,
)

FIXTURES = Path(__file__).parent / "fixtures"


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-skill",
        description="A test skill for AgentShift Vertex AI",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# Basic file creation
# ---------------------------------------------------------------------------


class TestVertexEmitterBasic:
    def test_creates_agent_json(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "agent.json").exists()

    def test_creates_readme_md(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "README.md").exists()

    def test_creates_output_directory_if_missing(self, tmp_path):
        ir = make_simple_ir()
        target = tmp_path / "deep" / "nested" / "dir"
        assert not target.exists()
        emit(ir, target)
        assert target.exists()


# ---------------------------------------------------------------------------
# agent.json structure
# ---------------------------------------------------------------------------


class TestVertexAgentJson:
    def test_agent_json_is_valid_json(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        raw = (tmp_path / "agent.json").read_text()
        data = json.loads(raw)  # must not raise
        assert isinstance(data, dict)

    def test_display_name_matches_ir_name(self, tmp_path):
        ir = make_simple_ir(name="my-agent")
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert data["displayName"] == "my-agent"

    def test_goal_contains_system_prompt(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="You are a test bot."))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert "You are a test bot." in data["goal"]

    def test_goal_within_8000_chars(self, tmp_path):
        long_prompt = "This is a sentence. " * 500  # ~10000 chars
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["goal"]) <= 8000

    def test_instructions_is_list(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert isinstance(data["instructions"], list)

    def test_instructions_populated_from_prompt(self, tmp_path):
        prompt = "Step one.\nStep two.\nStep three."
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["instructions"]) >= 1

    def test_instructions_max_20(self, tmp_path):
        prompt = "\n".join(f"Instruction {i}." for i in range(50))
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["instructions"]) <= 20

    def test_instructions_each_max_500_chars(self, tmp_path):
        long_line = "x" * 1000
        ir = make_simple_ir(persona=Persona(system_prompt=long_line))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        for instr in data["instructions"]:
            assert len(instr) <= 500

    def test_default_language_code_en(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert data["defaultLanguageCode"] == "en"

    def test_supported_language_codes_contains_en(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert "en" in data["supportedLanguageCodes"]

    def test_tools_populated_from_ir(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="gh", description="GitHub CLI", kind="shell"),
                Tool(name="slack", description="Slack MCP", kind="mcp"),
            ]
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        names = [t["name"] for t in data["tools"]]
        assert "gh" in names
        assert "slack" in names

    def test_shell_tool_type_is_function(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        tool = next(t for t in data["tools"] if t["name"] == "gh")
        assert tool["type"] == "FUNCTION"

    def test_shell_tool_has_stub_marker(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        tool = next(t for t in data["tools"] if t["name"] == "gh")
        assert "x-agentshift-stub" in tool
        assert "Cloud Function" in tool["x-agentshift-stub"]

    def test_mcp_tool_has_stub_marker(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="slack", description="Slack MCP", kind="mcp")])
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        tool = next(t for t in data["tools"] if t["name"] == "slack")
        assert "x-agentshift-stub" in tool
        assert "MCP" in tool["x-agentshift-stub"]

    def test_openapi_tool_type_is_open_api(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="weather", description="Weather API", kind="openapi")])
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        tool = next(t for t in data["tools"] if t["name"] == "weather")
        assert tool["type"] == "OPEN_API"

    def test_openapi_tool_no_stub_marker(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="weather", description="Weather API", kind="openapi")])
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        tool = next(t for t in data["tools"] if t["name"] == "weather")
        assert "x-agentshift-stub" not in tool

    def test_no_tools_produces_empty_list(self, tmp_path):
        ir = make_simple_ir(tools=[])
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert data["tools"] == []

    def test_goal_falls_back_to_description_when_no_prompt(self, tmp_path):
        ir = make_simple_ir(
            description="A fallback description agent",
            persona=Persona(system_prompt=None),
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert "fallback description" in data["goal"]

    def test_headings_excluded_from_instructions(self, tmp_path):
        prompt = "# Main Heading\n## Sub Heading\nActual instruction line."
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        for instr in data["instructions"]:
            assert not instr.startswith("#")


# ---------------------------------------------------------------------------
# No raw Python reprs
# ---------------------------------------------------------------------------


class TestNoRawPythonReprs:
    def test_no_python_repr_in_agent_json(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        content = (tmp_path / "agent.json").read_text()
        assert "<agentshift." not in content
        assert "object at 0x" not in content

    def test_no_python_repr_in_readme(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "<agentshift." not in readme
        assert "object at 0x" not in readme


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


class TestVertexReadme:
    def test_readme_mentions_agent_name(self, tmp_path):
        ir = make_simple_ir(name="my-agent")
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "my-agent" in readme

    def test_readme_mentions_agentshift(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "AgentShift" in readme or "agentshift" in readme.lower()

    def test_readme_has_gcloud_deploy_command(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "gcloud" in readme

    def test_readme_mentions_vertex_ai(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Vertex AI" in readme

    def test_readme_mentions_tools_when_present(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "gh" in readme

    def test_readme_mentions_knowledge_when_present(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="guide", kind="file", path="/tmp/guide.md")]
        )
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Knowledge" in readme

    def test_readme_mentions_cloud_scheduler_for_cron(self, tmp_path):
        ir = make_simple_ir(
            triggers=[Trigger(id="daily", kind="cron", cron_expr="0 9 * * *", message="Run daily")]
        )
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Cloud Scheduler" in readme or "scheduler" in readme.lower()


# ---------------------------------------------------------------------------
# Real skills (skipped if not installed)
# ---------------------------------------------------------------------------


class TestVertexRealSkills:
    _GITHUB_SKILL = (
        Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
    )

    def test_github_skill_creates_agent_json(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(self._GITHUB_SKILL)
        emit(ir, tmp_path)
        assert (tmp_path / "agent.json").exists()

    def test_github_skill_creates_readme(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(self._GITHUB_SKILL)
        emit(ir, tmp_path)
        assert (tmp_path / "README.md").exists()

    def test_github_skill_agent_json_is_valid(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(self._GITHUB_SKILL)
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert isinstance(data, dict)
        assert "displayName" in data
        assert "goal" in data
        assert "instructions" in data

    def test_github_skill_goal_within_limit(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(self._GITHUB_SKILL)
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["goal"]) <= 8000

    def test_github_skill_tools_in_agent_json(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(self._GITHUB_SKILL)
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        shell_tools = [t for t in ir.tools if t.kind == "shell"]
        tool_names = [t["name"] for t in data["tools"]]
        for tool in shell_tools:
            assert tool.name in tool_names
