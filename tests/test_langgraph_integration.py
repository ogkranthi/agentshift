"""Integration tests: pregnancy-companion OpenClaw fixture → LangGraph emitter."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agentshift.emitters.langgraph import emit
from agentshift.parsers.openclaw import parse_skill_dir

_VENV_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "agentshift"
_AGENTSHIFT = (
    [str(_VENV_BIN)] if _VENV_BIN.exists() else [sys.executable, "-m", "agentshift"]
)

FIXTURES = Path(__file__).parent / "fixtures"
PREGNANCY = FIXTURES / "pregnancy-companion"

OUTPUT_FILES = {
    "agent.py",
    "tools.py",
    "requirements.txt",
    "langgraph.json",
    ".env.example",
    "README.md",
}


# ---------------------------------------------------------------------------
# T12-1: pregnancy-companion → langgraph
# ---------------------------------------------------------------------------


def test_pregnancy_companion_to_langgraph(tmp_path):
    """pregnancy-companion skill converts to LangGraph — all 6 files created."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"Missing output file: {fname}"


def test_pregnancy_companion_langgraph_agent_py_structure(tmp_path):
    """agent.py from pregnancy-companion has StateGraph, ToolNode, build_graph, compile."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "StateGraph" in content
    assert "ToolNode" in content
    assert "build_graph" in content
    assert "compile" in content


def test_pregnancy_companion_langgraph_readme_has_skill_name(tmp_path):
    """README.md mentions the pregnancy-companion skill name."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "pregnancy-companion" in content or "pregnancy_companion" in content


def test_pregnancy_companion_langgraph_manifest_valid(tmp_path):
    """langgraph.json is valid JSON with graphs key for pregnancy-companion."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    raw = (tmp_path / "langgraph.json").read_text()
    data = json.loads(raw)
    assert "graphs" in data
    assert isinstance(data["graphs"], dict)
    assert len(data["graphs"]) >= 1


def test_pregnancy_companion_langgraph_requirements(tmp_path):
    """requirements.txt has langgraph and langchain-core for pregnancy-companion."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "langgraph" in content
    assert "langchain-core" in content


def test_pregnancy_companion_langgraph_env_example(tmp_path):
    """`.env.example` exists and has ANTHROPIC_API_KEY for pregnancy-companion."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    content = (tmp_path / ".env.example").read_text()
    assert "ANTHROPIC_API_KEY" in content


def test_pregnancy_companion_langgraph_tools_py(tmp_path):
    """tools.py is created and has get_tools() for pregnancy-companion."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "get_tools" in content


def test_pregnancy_companion_langgraph_agent_py_has_system_prompt(tmp_path):
    """agent.py contains the skill's system prompt."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "_SYSTEM_PROMPT" in content


def test_pregnancy_companion_langgraph_no_python_repr(tmp_path):
    """No raw Python object reprs appear in any generated file."""
    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        content = (tmp_path / fname).read_text()
        assert "<agentshift." not in content, f"Python repr in {fname}"
        assert "object at 0x" not in content, f"Memory address in {fname}"


# ---------------------------------------------------------------------------
# T12-2: CLI convert command with pregnancy-companion → langgraph
# ---------------------------------------------------------------------------


def test_pregnancy_companion_cli_convert_to_langgraph(tmp_path):
    """CLI `agentshift convert --to langgraph pregnancy-companion` succeeds."""
    result = subprocess.run(
        [
            *_AGENTSHIFT,
            "convert",
            str(PREGNANCY),
            "--from",
            "openclaw",
            "--to",
            "langgraph",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"CLI did not create: {fname}"
