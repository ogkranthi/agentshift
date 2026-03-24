"""Tests for the Copilot emitter — IR → .agent.md"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentshift.emitters.copilot import emit
from agentshift.ir import (
    AgentIR,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
)

FIXTURES = Path(__file__).parent / "fixtures"


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-skill",
        description="A test skill for AgentShift",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


class TestCopilotEmitterBasic:
    def test_creates_agent_md(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "test-skill.agent.md").exists()

    def test_creates_readme(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "README.md").exists()

    def test_agent_md_has_frontmatter(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert content.startswith("---")
        assert "name:" in content
        assert "description:" in content
        assert "model:" in content
        assert "tools:" in content

    def test_agent_md_has_instructions_body(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "You are a helpful assistant." in content

    def test_name_in_frontmatter(self, tmp_path):
        ir = make_simple_ir(name="weather")
        emit(ir, tmp_path)
        content = (tmp_path / "weather.agent.md").read_text()
        assert 'name: "weather"' in content

    def test_description_in_frontmatter(self, tmp_path):
        ir = make_simple_ir(description="Get the weather for any city")
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "Get the weather for any city" in content

    def test_default_models_included(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "Claude Sonnet 4.6 (copilot)" in content
        assert "Claude Opus 4.6 (copilot)" in content
        assert "GPT-5.3-Codex" in content


class TestCopilotEmitterTools:
    def test_shell_tool_maps_to_run_in_terminal(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "execute/runInTerminal" in content

    def test_mcp_tool_adds_comment(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="slack", description="Slack MCP", kind="mcp")])
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "MCP" in content
        assert "slack" in content

    def test_knowledge_adds_read_file(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[
                KnowledgeSource(
                    name="guide", kind="file", path="~/.openclaw/skills/x/knowledge/guide.md"
                )
            ]
        )
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "read/readFile" in content

    def test_no_tools_produces_empty_list(self, tmp_path):
        ir = make_simple_ir(tools=[])
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "tools:" in content

    def test_curl_tool_adds_web(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="curl", description="HTTP", kind="shell")])
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        # curl → web tool
        assert "web" in content


class TestCopilotEmitterReadme:
    def test_readme_contains_skill_name(self, tmp_path):
        ir = make_simple_ir(name="github")
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "github" in readme

    def test_readme_mentions_vscode(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "VS Code" in readme or "vscode" in readme.lower()

    def test_readme_mentions_agentshift(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "AgentShift" in readme

    def test_readme_mentions_mcp_when_mcp_tools(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="slack", description="Slack", kind="mcp")])
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "MCP" in readme or "slack" in readme


class TestCopilotEmitterRealSkills:
    def test_github_skill_converts(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
        if not skill.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)
        content = (tmp_path / "github.agent.md").read_text()
        assert "github" in content
        assert "execute/runInTerminal" in content

    def test_slack_skill_converts(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/slack"
        if not skill.exists():
            pytest.skip("slack skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)
        content = (tmp_path / "slack.agent.md").read_text()
        assert "slack" in content.lower()

    def test_weather_skill_converts(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/weather"
        if not skill.exists():
            pytest.skip("weather skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)
        assert (tmp_path / "weather.agent.md").exists()
        content = (tmp_path / "weather.agent.md").read_text()
        assert len(content) > 200

    def test_output_is_valid_utf8(self, tmp_path):
        ir = make_simple_ir(name="unicode-test", description="Émojis 🎉 and ünïcödé")
        emit(ir, tmp_path)
        content = (tmp_path / "unicode-test.agent.md").read_bytes()
        content.decode("utf-8")  # should not raise

    def test_no_raw_python_reprs(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        content = (tmp_path / "test-skill.agent.md").read_text()
        assert "<agentshift." not in content
        assert "object at 0x" not in content
