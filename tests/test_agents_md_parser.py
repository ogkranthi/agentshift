"""Tests for the AGENTS.md parser (src/agentshift/parsers/agents_md.py).

Covers:
- Parse from file path and directory
- Name/description extraction
- Section → IR mapping (architecture, commands, style, do-not, testing)
- Tool extraction from bullets and code blocks
- Guardrail extraction
- Round-trip: agents-md → IR → claude-code / copilot
- CLI integration
- Edge cases (empty file, missing file, no headings)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentshift.ir import AgentIR
from agentshift.parsers import agents_md

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "agents-md-sample"
FIXTURE_FILE = FIXTURES_DIR / "AGENTS.md"


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------


class TestParseFromFile:
    """Parse AGENTS.md directly by file path."""

    def test_parse_file_returns_agent_ir(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert isinstance(ir, AgentIR)

    def test_name_from_h1(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert ir.name == "fastapi-inventory-service"

    def test_description_from_first_paragraph(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert "inventory" in ir.description.lower()

    def test_source_platform(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert ir.metadata.source_platform == "agents-md"

    def test_source_file_recorded(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert "AGENTS.md" in ir.metadata.source_file


class TestParseFromDirectory:
    """Parse by passing a directory that contains AGENTS.md."""

    def test_parse_directory_returns_agent_ir(self):
        ir = agents_md.parse(FIXTURES_DIR)
        assert isinstance(ir, AgentIR)

    def test_directory_parse_finds_agents_md(self):
        ir = agents_md.parse(FIXTURES_DIR)
        assert ir.name == "fastapi-inventory-service"


# ---------------------------------------------------------------------------
# Section → IR mapping
# ---------------------------------------------------------------------------


class TestArchitectureSection:
    """Architecture section → persona.system_prompt."""

    def test_architecture_in_system_prompt(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert ir.persona.system_prompt is not None
        assert "FastAPI" in ir.persona.system_prompt

    def test_architecture_prepended(self):
        ir = agents_md.parse(FIXTURE_FILE)
        # Architecture should appear early in the prompt
        prompt = ir.persona.system_prompt
        arch_idx = prompt.find("Architecture")
        assert arch_idx >= 0
        # Should be before style section
        style_idx = prompt.find("Code Style")
        if style_idx >= 0:
            assert arch_idx < style_idx


class TestCommandsSection:
    """Commands section → tools (kind=shell)."""

    def test_tools_extracted(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert len(ir.tools) > 0

    def test_tools_are_shell_kind(self):
        ir = agents_md.parse(FIXTURE_FILE)
        for tool in ir.tools:
            assert tool.kind == "shell"

    def test_uvicorn_extracted(self):
        ir = agents_md.parse(FIXTURE_FILE)
        names = {t.name for t in ir.tools}
        assert "uvicorn" in names

    def test_pytest_extracted(self):
        ir = agents_md.parse(FIXTURE_FILE)
        names = {t.name for t in ir.tools}
        assert "pytest" in names

    def test_ruff_extracted(self):
        ir = agents_md.parse(FIXTURE_FILE)
        names = {t.name for t in ir.tools}
        assert "ruff" in names

    def test_binary_name_extracted_from_commands(self):
        ir = agents_md.parse(FIXTURE_FILE)
        # alembic should be extracted
        names = {t.name for t in ir.tools}
        assert "alembic" in names

    def test_tool_descriptions_contain_command(self):
        ir = agents_md.parse(FIXTURE_FILE)
        uvicorn_tools = [t for t in ir.tools if t.name == "uvicorn"]
        assert len(uvicorn_tools) >= 1
        assert "uvicorn" in uvicorn_tools[0].description


class TestDoNotSection:
    """Do NOT section → governance.guardrails + constraints.guardrails."""

    def test_guardrails_extracted(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert len(ir.governance.guardrails) > 0

    def test_guardrail_count(self):
        ir = agents_md.parse(FIXTURE_FILE)
        # Fixture has 5 Do NOT rules
        assert len(ir.governance.guardrails) >= 3

    def test_guardrail_text_content(self):
        ir = agents_md.parse(FIXTURE_FILE)
        texts = [g.text for g in ir.governance.guardrails]
        assert any("migration" in t.lower() or "alembic" in t.lower() for t in texts)

    def test_guardrail_refs_in_constraints(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert len(ir.constraints.guardrails) > 0
        assert all(ref.startswith("agents-md-rule-") for ref in ir.constraints.guardrails)


class TestStyleSection:
    """Style section → persona.system_prompt."""

    def test_style_in_system_prompt(self):
        ir = agents_md.parse(FIXTURE_FILE)
        assert "type hints" in ir.persona.system_prompt.lower()


class TestTestingSection:
    """Testing section → tools extracted."""

    def test_testing_commands_extracted(self):
        ir = agents_md.parse(FIXTURE_FILE)
        descriptions = " ".join(t.description for t in ir.tools)
        # pytest commands from the Testing section code block
        assert "pytest" in descriptions


# ---------------------------------------------------------------------------
# Round-trip: agents-md → IR → claude-code
# ---------------------------------------------------------------------------


class TestRoundTripClaudeCode:
    """agents-md → IR → claude-code emitter produces CLAUDE.md."""

    def test_emit_claude_code(self, tmp_path):
        from agentshift.emitters import claude_code as cc_emitter

        ir = agents_md.parse(FIXTURE_FILE)
        cc_emitter.emit(ir, tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert len(content) > 0

    def test_claude_code_has_content(self, tmp_path):
        from agentshift.emitters import claude_code as cc_emitter

        ir = agents_md.parse(FIXTURE_FILE)
        cc_emitter.emit(ir, tmp_path)

        content = (tmp_path / "CLAUDE.md").read_text()
        # Should contain architecture info
        assert "fastapi" in content.lower() or "inventory" in content.lower()


# ---------------------------------------------------------------------------
# Round-trip: agents-md → IR → copilot
# ---------------------------------------------------------------------------


class TestRoundTripCopilot:
    """agents-md → IR → copilot emitter produces .agent.md."""

    def test_emit_copilot(self, tmp_path):
        from agentshift.emitters import copilot as copilot_emitter

        ir = agents_md.parse(FIXTURE_FILE)
        copilot_emitter.emit(ir, tmp_path)

        agent_files = list(tmp_path.glob("*.agent.md"))
        assert len(agent_files) >= 1

    def test_copilot_agent_md_created(self, tmp_path):
        from agentshift.emitters import copilot as copilot_emitter

        ir = agents_md.parse(FIXTURE_FILE)
        copilot_emitter.emit(ir, tmp_path)

        agent_files = list(tmp_path.glob("*.agent.md"))
        content = agent_files[0].read_text()
        assert len(content) > 0


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    """CLI round-trip: agentshift convert --from agents-md."""

    def test_cli_convert_claude_code(self, tmp_path):
        from typer.testing import CliRunner

        from agentshift.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "convert",
                str(FIXTURES_DIR),
                "--from",
                "agents-md",
                "--to",
                "claude-code",
                "--output",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0

    def test_cli_diff(self, tmp_path):
        from typer.testing import CliRunner

        from agentshift.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "diff",
                str(FIXTURES_DIR),
                "--from",
                "agents-md",
            ],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_agents_md(self, tmp_path):
        md = tmp_path / "AGENTS.md"
        md.write_text("")
        ir = agents_md.parse(md)
        assert isinstance(ir, AgentIR)
        assert ir.name is not None

    def test_no_headings(self, tmp_path):
        md = tmp_path / "AGENTS.md"
        md.write_text("Just some text without any headings.\nAnother line.")
        ir = agents_md.parse(md)
        assert isinstance(ir, AgentIR)

    def test_directory_without_agents_md_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match=r"No AGENTS\.md found"):
            agents_md.parse(tmp_path)

    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            agents_md.parse(Path("/nonexistent/path/to/nothing"))

    def test_h1_only_no_sections(self, tmp_path):
        md = tmp_path / "AGENTS.md"
        md.write_text("# My Agent\n\nA simple agent with no sections.\n")
        ir = agents_md.parse(md)
        assert ir.name == "my-agent"
        assert "simple agent" in ir.description.lower()

    def test_h3_fallback(self, tmp_path):
        md = tmp_path / "AGENTS.md"
        md.write_text("# Agent\n\nDesc.\n\n### Commands\n\n- Run: python main.py\n")
        ir = agents_md.parse(md)
        assert len(ir.tools) >= 1

    def test_code_block_extraction(self, tmp_path):
        md = tmp_path / "AGENTS.md"
        md.write_text("# Agent\n\nDesc.\n\n## Commands\n\n```bash\nnpm install\nnpm start\n```\n")
        ir = agents_md.parse(md)
        names = {t.name for t in ir.tools}
        assert "npm" in names

    def test_name_fallback_to_directory(self, tmp_path):
        subdir = tmp_path / "my-cool-project"
        subdir.mkdir()
        md = subdir / "AGENTS.md"
        md.write_text("## Commands\n\n- Run: node index.js\n")
        ir = agents_md.parse(subdir)
        assert ir.name == "my-cool-project"
