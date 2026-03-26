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


class TestVertexInstructionTruncation:
    """Instruction/goal truncation boundary tests."""

    def test_goal_at_exactly_8000_chars_not_truncated(self, tmp_path):
        prompt = "x" * 8000
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["goal"]) == 8000

    def test_goal_at_8001_chars_truncated_to_8000(self, tmp_path):
        prompt = "x" * 8001
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["goal"]) == 8000

    def test_instructions_skip_empty_lines(self, tmp_path):
        prompt = "Line one.\n\n\nLine two.\n\n"
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        for instr in data["instructions"]:
            assert instr.strip() != ""

    def test_instructions_each_at_most_500_chars_from_long_line(self, tmp_path):
        # A single 1000-char line should be truncated to 500 in instructions
        prompt = "A" * 1000
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        for instr in data["instructions"]:
            assert len(instr) <= 500

    def test_goal_falls_back_to_description_length(self, tmp_path):
        desc = "x" * 100
        ir = make_simple_ir(description=desc, persona=Persona(system_prompt=None))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["goal"]) == 100


class TestVertexMultipleToolTypes:
    """Tests with multiple tool types in a single agent."""

    def test_all_three_tool_types_in_tools_list(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="gh", description="GitHub CLI", kind="shell"),
                Tool(name="slack", description="Slack MCP", kind="mcp"),
                Tool(name="weather", description="Weather API", kind="openapi"),
            ]
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        names = {t["name"] for t in data["tools"]}
        assert "gh" in names
        assert "slack" in names
        assert "weather" in names

    def test_shell_tool_type_is_function_in_mixed(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="gh", description="GitHub CLI", kind="shell"),
                Tool(name="slack", description="Slack MCP", kind="mcp"),
                Tool(name="weather", description="Weather API", kind="openapi"),
            ]
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        by_name = {t["name"]: t for t in data["tools"]}
        assert by_name["gh"]["type"] == "FUNCTION"

    def test_mcp_tool_type_is_function_in_mixed(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="gh", description="GitHub CLI", kind="shell"),
                Tool(name="slack", description="Slack MCP", kind="mcp"),
                Tool(name="weather", description="Weather API", kind="openapi"),
            ]
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        by_name = {t["name"]: t for t in data["tools"]}
        assert by_name["slack"]["type"] == "FUNCTION"

    def test_openapi_tool_type_is_open_api_in_mixed(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="gh", description="GitHub CLI", kind="shell"),
                Tool(name="slack", description="Slack MCP", kind="mcp"),
                Tool(name="weather", description="Weather API", kind="openapi"),
            ]
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        by_name = {t["name"]: t for t in data["tools"]}
        assert by_name["weather"]["type"] == "OPEN_API"

    def test_only_shell_and_mcp_get_stub_markers(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="gh", description="GitHub CLI", kind="shell"),
                Tool(name="slack", description="Slack MCP", kind="mcp"),
                Tool(name="weather", description="Weather API", kind="openapi"),
            ]
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        by_name = {t["name"]: t for t in data["tools"]}
        assert "x-agentshift-stub" in by_name["gh"]
        assert "x-agentshift-stub" in by_name["slack"]
        assert "x-agentshift-stub" not in by_name["weather"]

    def test_mcp_stub_includes_description(self, tmp_path):
        ir = make_simple_ir(
            tools=[Tool(name="slack", description="Send Slack messages via MCP", kind="mcp")]
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        tool = next(t for t in data["tools"] if t["name"] == "slack")
        # D14: description should appear in the stub value
        assert "Send Slack messages via MCP" in tool["x-agentshift-stub"]


class TestVertexKnowledgeSources:
    """Knowledge source handling in Vertex AI emitter."""

    def test_single_knowledge_source_in_readme(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="my-docs", kind="file", path="/tmp/docs.md")]
        )
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "my-docs" in readme

    def test_multiple_knowledge_sources_all_in_readme(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[
                KnowledgeSource(name="guide1", kind="file", path="/tmp/guide1.md"),
                KnowledgeSource(name="guide2", kind="url", path="https://example.com"),
            ]
        )
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "guide1" in readme
        assert "guide2" in readme

    def test_knowledge_source_readme_has_vertex_search_reference(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="docs", kind="file", path="/tmp/docs.md")]
        )
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Vertex AI" in readme or "data store" in readme.lower()

    def test_no_knowledge_no_knowledge_section(self, tmp_path):
        ir = make_simple_ir(knowledge=[])
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "## Knowledge" not in readme


class TestVertexInstructionExtraction:
    """Tests for how instructions are extracted from the system prompt."""

    def test_multi_line_prompt_yields_multiple_instructions(self, tmp_path):
        prompt = "Do step one.\nDo step two.\nDo step three."
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["instructions"]) == 3

    def test_heading_lines_excluded(self, tmp_path):
        prompt = "## Instructions\nDo step one.\n### Sub-heading\nDo step two."
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        for instr in data["instructions"]:
            assert not instr.startswith("#")

    def test_50_line_prompt_capped_at_20_instructions(self, tmp_path):
        prompt = "\n".join(f"Instruction line {i}." for i in range(50))
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert len(data["instructions"]) == 20

    def test_empty_prompt_yields_empty_instructions(self, tmp_path):
        ir = make_simple_ir(
            description="My agent", persona=Persona(system_prompt=None)
        )
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "agent.json").read_text())
        assert data["instructions"] == []


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
