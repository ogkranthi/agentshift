"""Tests for the Copilot emitter — IR → .agent.md"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

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
                    name="guide",
                    kind="file",
                    path="~/.openclaw/skills/x/knowledge/guide.md",
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


class TestCopilotAgentMdSchema:
    """Validate generated .agent.md YAML frontmatter structure and cleanliness.

    Requirements:
    - name: string (present, non-empty)
    - description: string (present)
    - model: list (present, non-empty)
    - tools: list (present)
    - No Python reprs anywhere
    - Frontmatter parses as clean YAML
    """

    _SKILLS_UNDER_TEST: ClassVar[list[str]] = [
        "github",
        "slack",
        "weather",
        "pregnancy-companion",
    ]
    _SKILL_BASE: ClassVar[Path] = (
        Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills"
    )
    _LOCAL_SKILLS: ClassVar[Path] = Path.home() / ".openclaw/skills"

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        """Extract and parse YAML frontmatter from .agent.md content."""
        import yaml

        if not content.startswith("---"):
            return {}
        end = content.find("---", 3)
        if end == -1:
            return {}
        fm_text = content[3:end].strip()
        return yaml.safe_load(fm_text) or {}

    @staticmethod
    def _get_agent_md(tmp_path: Path, ir) -> str:
        from agentshift.emitters.copilot import emit

        emit(ir, tmp_path)
        files = list(tmp_path.glob("*.agent.md"))
        assert len(files) == 1, f"Expected 1 .agent.md, got {files}"
        return files[0].read_text()

    # -----------------------------------------------------------------------
    # Frontmatter field tests (using synthetic IR)
    # -----------------------------------------------------------------------

    def test_name_present_and_is_string(self, tmp_path):
        ir = make_simple_ir(name="test-skill")
        content = self._get_agent_md(tmp_path, ir)
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("name"), str)
        assert fm["name"]  # non-empty

    def test_description_present_and_is_string(self, tmp_path):
        ir = make_simple_ir(description="A helpful agent for testing")
        content = self._get_agent_md(tmp_path, ir)
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("description"), str)
        assert fm["description"]

    def test_model_present_and_is_list(self, tmp_path):
        ir = make_simple_ir()
        content = self._get_agent_md(tmp_path, ir)
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("model"), list)
        assert len(fm["model"]) > 0

    def test_tools_present_and_is_list(self, tmp_path):
        ir = make_simple_ir()
        content = self._get_agent_md(tmp_path, ir)
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("tools"), list)

    def test_frontmatter_no_python_reprs(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        content = self._get_agent_md(tmp_path, ir)
        fm_text = content[3 : content.find("---", 3)]
        assert "<agentshift." not in fm_text
        assert "object at 0x" not in fm_text

    def test_frontmatter_yaml_parses_cleanly(self, tmp_path):
        import yaml

        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        content = self._get_agent_md(tmp_path, ir)
        assert content.startswith("---")
        end = content.find("---", 3)
        fm_text = content[3:end].strip()
        # Should not raise
        parsed = yaml.safe_load(fm_text)
        assert parsed is not None

    def test_body_contains_system_prompt(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="You are an expert assistant."))
        content = self._get_agent_md(tmp_path, ir)
        # Body is after the second ---
        end = content.find("---", 3)
        body = content[end + 3 :]
        assert "You are an expert assistant." in body

    # -----------------------------------------------------------------------
    # Real skill tests (skipped if not installed)
    # -----------------------------------------------------------------------

    def _find_skill(self, name: str) -> Path | None:
        candidates = [
            self._SKILL_BASE / name,
            self._LOCAL_SKILLS / name,
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def test_github_skill_frontmatter_valid(self, tmp_path):
        from agentshift.emitters.copilot import emit as copilot_emit
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = self._find_skill("github")
        if skill is None:
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        copilot_emit(ir, tmp_path)
        files = list(tmp_path.glob("*.agent.md"))
        assert files
        content = files[0].read_text()
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("name"), str) and fm["name"]
        assert isinstance(fm.get("description"), str)
        assert isinstance(fm.get("model"), list) and len(fm["model"]) > 0
        assert isinstance(fm.get("tools"), list)

    def test_github_skill_no_python_reprs(self, tmp_path):
        from agentshift.emitters.copilot import emit as copilot_emit
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = self._find_skill("github")
        if skill is None:
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        copilot_emit(ir, tmp_path)
        for f in tmp_path.glob("*.agent.md"):
            text = f.read_text()
            assert "<agentshift." not in text, f"Python repr in {f.name}"
            assert "object at 0x" not in text, f"Python repr in {f.name}"

    def test_slack_skill_frontmatter_valid(self, tmp_path):
        from agentshift.emitters.copilot import emit as copilot_emit
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = self._find_skill("slack")
        if skill is None:
            pytest.skip("slack skill not installed")
        ir = parse_skill_dir(skill)
        copilot_emit(ir, tmp_path)
        files = list(tmp_path.glob("*.agent.md"))
        assert files
        content = files[0].read_text()
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("name"), str) and fm["name"]
        assert isinstance(fm.get("model"), list) and len(fm["model"]) > 0

    def test_weather_skill_frontmatter_valid(self, tmp_path):
        from agentshift.emitters.copilot import emit as copilot_emit
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = self._find_skill("weather")
        if skill is None:
            pytest.skip("weather skill not installed")
        ir = parse_skill_dir(skill)
        copilot_emit(ir, tmp_path)
        files = list(tmp_path.glob("*.agent.md"))
        assert files
        content = files[0].read_text()
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("name"), str) and fm["name"]
        assert isinstance(fm.get("model"), list)

    def test_pregnancy_companion_skill_frontmatter_valid(self, tmp_path):
        from agentshift.emitters.copilot import emit as copilot_emit
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = self._find_skill("pregnancy-companion")
        if skill is None:
            pytest.skip("pregnancy-companion skill not installed")
        ir = parse_skill_dir(skill)
        copilot_emit(ir, tmp_path)
        files = list(tmp_path.glob("*.agent.md"))
        assert files
        content = files[0].read_text()
        fm = self._parse_frontmatter(content)
        assert isinstance(fm.get("name"), str) and fm["name"]
        assert isinstance(fm.get("description"), str)
        assert isinstance(fm.get("model"), list) and len(fm["model"]) > 0
        assert isinstance(fm.get("tools"), list)

    def test_pregnancy_companion_no_python_reprs(self, tmp_path):
        from agentshift.emitters.copilot import emit as copilot_emit
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = self._find_skill("pregnancy-companion")
        if skill is None:
            pytest.skip("pregnancy-companion skill not installed")
        ir = parse_skill_dir(skill)
        copilot_emit(ir, tmp_path)
        for f in tmp_path.glob("*.agent.md"):
            text = f.read_text()
            assert "<agentshift." not in text, f"Python repr in {f.name}"
            assert "object at 0x" not in text, f"Python repr in {f.name}"


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
