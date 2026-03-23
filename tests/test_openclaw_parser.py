"""Tests for the OpenClaw SKILL.md parser."""

from pathlib import Path

import pytest

from agentshift.parsers.openclaw import parse_skill_dir
from agentshift.ir import AgentIR

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_simple_skill():
    ir = parse_skill_dir(FIXTURES / "simple-skill")
    assert isinstance(ir, AgentIR)
    assert ir.name == "weather-lookup"
    assert "weather" in ir.description.lower()


def test_parse_simple_skill_homepage():
    ir = parse_skill_dir(FIXTURES / "simple-skill")
    assert ir.homepage == "https://wttr.in/:help"


def test_parse_tool_heavy_skill():
    ir = parse_skill_dir(FIXTURES / "tool-heavy-skill")
    assert isinstance(ir, AgentIR)
    tool_names = [t.name for t in ir.tools]
    # bash extracted from ```bash block
    assert "bash" in tool_names
    # MCP tools extracted from body mentions
    assert "slack" in tool_names
    assert "github" in tool_names
    assert "linear" in tool_names
    assert len(ir.tools) >= 3


def test_parse_tool_heavy_skill_kinds():
    ir = parse_skill_dir(FIXTURES / "tool-heavy-skill")
    kinds = {t.name: t.kind for t in ir.tools}
    assert kinds["bash"] == "shell"
    assert kinds["slack"] == "mcp"
    assert kinds["github"] == "mcp"
    assert kinds["linear"] == "mcp"


def test_parse_cron_skill():
    ir = parse_skill_dir(FIXTURES / "cron-knowledge-skill")
    assert isinstance(ir, AgentIR)
    assert ir.name == "daily-standup"
    assert "standup" in ir.description.lower()
    # Body mentions cron — verify the system prompt captures it
    assert ir.persona.system_prompt is not None
    assert "cron" in ir.persona.system_prompt.lower()
    # Note: cron trigger extraction from SKILL.md body is not yet implemented in the parser;
    # triggers come from ~/.openclaw/cron/jobs.json (external to SKILL.md).


def test_parse_cron_skill_knowledge():
    ir = parse_skill_dir(FIXTURES / "cron-knowledge-skill")
    assert len(ir.knowledge) >= 1
    ks_names = [k.name for k in ir.knowledge]
    assert "team" in ks_names


def test_source_platform():
    for fixture in ["simple-skill", "tool-heavy-skill", "cron-knowledge-skill"]:
        ir = parse_skill_dir(FIXTURES / fixture)
        assert ir.metadata.source_platform == "openclaw"


def test_missing_skill_md_raises():
    with pytest.raises(FileNotFoundError):
        parse_skill_dir(FIXTURES / "nonexistent-skill")


def test_parse_cron_skill_os_constraints():
    ir = parse_skill_dir(FIXTURES / "cron-knowledge-skill")
    assert "darwin" in ir.constraints.supported_os
    assert "linux" in ir.constraints.supported_os
