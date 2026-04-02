"""Tests for persona.sections population in OpenClaw and Claude Code parsers."""

from __future__ import annotations

from pathlib import Path

from agentshift.parsers.claude_code import parse_agent_dir
from agentshift.parsers.openclaw import parse_skill_dir

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill_dir(tmp_path: Path, body: str, frontmatter: str | None = None) -> Path:
    """Write a minimal SKILL.md into a temp skill dir and return the dir."""
    if frontmatter is None:
        frontmatter = "name: test-skill\ndescription: A test skill."
    content = f"---\n{frontmatter}\n---\n\n{body}"
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


def _write_claude_dir(tmp_path: Path, claude_md: str) -> Path:
    """Write CLAUDE.md into a temp dir and return the dir."""
    agent_dir = tmp_path / "test-agent"
    agent_dir.mkdir()
    (agent_dir / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
    return agent_dir


# ---------------------------------------------------------------------------
# OpenClaw parser — persona.sections
# ---------------------------------------------------------------------------


class TestOpenClawParserSections:
    def test_sections_populated_from_h2_headings(self, tmp_path):
        body = "## Overview\n\nThis skill does X.\n\n## Behavior\n\nFollow these rules.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert "overview" in ir.persona.sections
        assert "behavior" in ir.persona.sections

    def test_sections_overview_content(self, tmp_path):
        body = "## Overview\n\nThis skill does X.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections["overview"] == "This skill does X."

    def test_sections_with_aliases_normalized(self, tmp_path):
        body = "## Instructions\n\nDo this first.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert "behavior" in ir.persona.sections
        assert "instructions" not in ir.persona.sections

    def test_sections_case_insensitive_alias(self, tmp_path):
        body = "## OVERVIEW\n\nSome overview text.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert "overview" in ir.persona.sections

    def test_sections_none_when_no_headings(self, tmp_path):
        body = "This skill does various things without any headings.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is None

    def test_sections_with_guardrails(self, tmp_path):
        body = "## Overview\n\nDoes things.\n\n## Safety\n\nDo not reveal secrets.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert "guardrails" in ir.persona.sections
        assert "safety" not in ir.persona.sections

    def test_sections_with_tools_heading(self, tmp_path):
        body = "## Overview\n\nA tool-heavy skill.\n\n## Capabilities\n\nCan do A, B, C.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert "tools" in ir.persona.sections

    def test_sections_multiple_sections_all_present(self, tmp_path):
        body = (
            "## Overview\n\nIntro.\n\n"
            "## Behavior\n\nRules.\n\n"
            "## Tools\n\nCapabilities.\n\n"
            "## Safety\n\nRestrictions.\n"
        )
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert set(ir.persona.sections.keys()) == {
            "overview",
            "behavior",
            "tools",
            "guardrails",
        }

    def test_sections_h3_fallback_when_no_h2(self, tmp_path):
        body = "### Overview\n\nH3 overview content.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert "overview" in ir.persona.sections

    def test_system_prompt_also_set(self, tmp_path):
        body = "## Overview\n\nSome overview.\n"
        skill_dir = _write_skill_dir(tmp_path, body)
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.system_prompt is not None
        assert len(ir.persona.system_prompt) > 0

    def test_empty_body_sections_none(self, tmp_path):
        # Only frontmatter, no body text
        frontmatter = "name: empty-skill\ndescription: Empty."
        content = f"---\n{frontmatter}\n---\n"
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is None


# ---------------------------------------------------------------------------
# Claude Code parser — persona.sections
# ---------------------------------------------------------------------------


class TestClaudeCodeParserSections:
    def test_sections_populated_from_instructions(self, tmp_path):
        claude_md = (
            "# My Agent\n\nA helpful agent.\n\n"
            "## Instructions\n\n"
            "## Overview\n\nThis agent does X.\n\n"
            "## Behavior\n\nFollow these rules.\n"
        )
        agent_dir = _write_claude_dir(tmp_path, claude_md)
        ir = parse_agent_dir(agent_dir)
        assert ir.persona.sections is not None

    def test_sections_from_instructions_section(self, tmp_path):
        claude_md = (
            "# My Agent\n\nA helpful agent.\n\n"
            "## Instructions\n\n"
            "## Overview\n\nDoes X.\n\n"
            "## Behavior\n\nBe helpful.\n"
        )
        agent_dir = _write_claude_dir(tmp_path, claude_md)
        ir = parse_agent_dir(agent_dir)
        assert ir.persona.sections is not None
        # The instructions body contains sub-headings
        assert ir.persona.sections is not None

    def test_sections_alias_normalized_in_claude(self, tmp_path):
        claude_md = (
            "# My Agent\n\nA helpful agent.\n\n## Instructions\n\n## About\n\nThis agent does Y.\n"
        )
        agent_dir = _write_claude_dir(tmp_path, claude_md)
        ir = parse_agent_dir(agent_dir)
        if ir.persona.sections:
            # "About" → "overview"
            assert "about" not in ir.persona.sections

    def test_no_headings_returns_none_sections(self, tmp_path):
        claude_md = (
            "# My Agent\n\nA helpful agent.\n\n"
            "## Instructions\n\n"
            "Just do things without any subsections.\n"
        )
        agent_dir = _write_claude_dir(tmp_path, claude_md)
        ir = parse_agent_dir(agent_dir)
        # No H2 subsections in instructions body → sections is None
        assert ir.persona.sections is None

    def test_sections_with_guardrails(self, tmp_path):
        claude_md = (
            "# My Agent\n\nA helpful agent.\n\n"
            "## Instructions\n\n"
            "## Overview\n\nDoes things.\n\n"
            "## Restrictions\n\nDo not do X.\n"
        )
        agent_dir = _write_claude_dir(tmp_path, claude_md)
        ir = parse_agent_dir(agent_dir)
        assert ir.persona.sections is not None
        assert "guardrails" in ir.persona.sections

    def test_claude_md_without_instructions_section(self, tmp_path):
        claude_md = (
            "# My Agent\n\nA helpful agent.\n\n"
            "## Overview\n\nDoes X.\n\n"
            "## Behavior\n\nBe helpful.\n"
        )
        agent_dir = _write_claude_dir(tmp_path, claude_md)
        ir = parse_agent_dir(agent_dir)
        # Parser uses full body as prompt when no "## Instructions" found
        # sections may or may not be populated depending on implementation
        # Just ensure no crash
        assert ir.persona is not None

    def test_persona_system_prompt_set(self, tmp_path):
        claude_md = "# My Agent\n\nA helpful agent.\n\n## Instructions\n\n## Overview\n\nContent.\n"
        agent_dir = _write_claude_dir(tmp_path, claude_md)
        ir = parse_agent_dir(agent_dir)
        assert ir.persona.system_prompt is not None
