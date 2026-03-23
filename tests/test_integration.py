"""Integration tests using the pregnancy-companion fixture."""

from pathlib import Path

from agentshift.emitters.claude_code import emit
from agentshift.ir import AgentIR
from agentshift.parsers.claude_code import parse_agent_dir
from agentshift.parsers.openclaw import parse_skill_dir

FIXTURES = Path(__file__).parent / "fixtures"
PREGNANCY = FIXTURES / "pregnancy-companion"


def test_pregnancy_companion_parses():
    """Pregnancy-companion fixture parses into a valid AgentIR."""
    ir = parse_skill_dir(PREGNANCY)
    assert isinstance(ir, AgentIR)
    assert ir.name == "pregnancy-companion"
    assert ir.description != ""
    assert ir.ir_version == "1.0"


def test_pregnancy_companion_metadata():
    ir = parse_skill_dir(PREGNANCY)
    assert ir.metadata.source_platform == "openclaw"
    assert ir.metadata.source_file is not None
    assert "SKILL.md" in ir.metadata.source_file


def test_pregnancy_companion_os_constraints():
    ir = parse_skill_dir(PREGNANCY)
    assert "darwin" in ir.constraints.supported_os
    assert "linux" in ir.constraints.supported_os


def test_pregnancy_companion_persona():
    ir = parse_skill_dir(PREGNANCY)
    assert ir.persona.system_prompt is not None
    assert len(ir.persona.system_prompt) > 100


def test_pregnancy_companion_to_claude_code(tmp_path):
    """Full convert pipeline: pregnancy-companion OpenClaw → Claude Code."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)

    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "settings.json").exists()

    claude_md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "pregnancy-companion" in claude_md.lower()


def test_pregnancy_companion_round_trip(tmp_path):
    """Pregnancy-companion survives a full round-trip."""
    ir_in = parse_skill_dir(PREGNANCY)
    emit(ir_in, tmp_path)
    ir_out = parse_agent_dir(tmp_path)

    assert ir_out.name == ir_in.name
    assert ir_out.description == ir_in.description
    assert ir_out.metadata.source_platform == "claude-code"


def test_pregnancy_companion_valid_ir_schema():
    """AgentIR produced from pregnancy-companion is valid (Pydantic validates on construction)."""
    ir = parse_skill_dir(PREGNANCY)
    # Re-serialize and re-parse to confirm schema validity
    data = ir.model_dump()
    ir2 = AgentIR(**data)
    assert ir2.name == ir.name
