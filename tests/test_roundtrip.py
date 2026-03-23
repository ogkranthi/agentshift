"""Round-trip tests: OpenClaw → IR → Claude Code → IR."""

from pathlib import Path

from agentshift.emitters.claude_code import emit
from agentshift.parsers.claude_code import parse_agent_dir
from agentshift.parsers.openclaw import parse_skill_dir

FIXTURES = Path(__file__).parent / "fixtures"


def test_openclaw_to_claude_code(tmp_path):
    """Parse simple fixture with openclaw parser, emit as Claude Code, parse back."""
    ir_in = parse_skill_dir(FIXTURES / "simple-skill")
    emit(ir_in, tmp_path)

    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "settings.json").exists()

    ir_out = parse_agent_dir(tmp_path)
    # Name survives round-trip (slugified from H1)
    assert ir_out.name == ir_in.name


def test_roundtrip_preserves_description(tmp_path):
    """Description survives OpenClaw → Claude Code round-trip."""
    ir_in = parse_skill_dir(FIXTURES / "simple-skill")
    emit(ir_in, tmp_path)

    ir_out = parse_agent_dir(tmp_path)
    assert ir_out.description == ir_in.description


def test_roundtrip_source_platform_updates(tmp_path):
    """After round-trip, source_platform reflects the last parser used."""
    ir_in = parse_skill_dir(FIXTURES / "simple-skill")
    assert ir_in.metadata.source_platform == "openclaw"

    emit(ir_in, tmp_path)
    ir_out = parse_agent_dir(tmp_path)
    assert ir_out.metadata.source_platform == "claude-code"


def test_roundtrip_tool_heavy(tmp_path):
    """Tool-heavy skill round-trips without error."""
    ir_in = parse_skill_dir(FIXTURES / "tool-heavy-skill")
    emit(ir_in, tmp_path)

    ir_out = parse_agent_dir(tmp_path)
    assert ir_out.name == ir_in.name
    # Tools are re-parsed from settings.json permissions
    assert len(ir_out.tools) >= 1


def test_roundtrip_ir_version(tmp_path):
    """IR version is preserved."""
    ir_in = parse_skill_dir(FIXTURES / "simple-skill")
    emit(ir_in, tmp_path)
    ir_out = parse_agent_dir(tmp_path)
    assert ir_out.ir_version == "1.0"
