"""CLI end-to-end tests using subprocess."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
PYTHON = sys.executable
_VENV_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "agentshift"
AGENTSHIFT = [str(_VENV_BIN)] if _VENV_BIN.exists() else [PYTHON, "-m", "agentshift"]


def run_convert(
    source: Path, tmp_path: Path, from_platform: str = "openclaw", to_platform: str = "claude-code"
) -> subprocess.CompletedProcess[str]:
    cmd = [
        *AGENTSHIFT,
        "convert",
        str(source),
        "--from",
        from_platform,
        "--to",
        to_platform,
        "--output",
        str(tmp_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(FIXTURES.parent.parent))


class TestCLIConvertSimple:
    def test_exit_code_zero(self, tmp_path):
        result = run_convert(FIXTURES / "simple-skill", tmp_path)
        assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

    def test_claude_md_created(self, tmp_path):
        run_convert(FIXTURES / "simple-skill", tmp_path)
        assert (tmp_path / "CLAUDE.md").exists()

    def test_settings_json_created(self, tmp_path):
        run_convert(FIXTURES / "simple-skill", tmp_path)
        assert (tmp_path / "settings.json").exists()

    def test_claude_md_contains_skill_name(self, tmp_path):
        run_convert(FIXTURES / "simple-skill", tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "weather" in content.lower()

    def test_settings_json_is_valid_json(self, tmp_path):
        run_convert(FIXTURES / "simple-skill", tmp_path)
        data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert isinstance(data, dict)


class TestCLIConvertToolHeavy:
    def test_exit_code_zero(self, tmp_path):
        result = run_convert(FIXTURES / "tool-heavy-skill", tmp_path)
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_claude_md_contains_skill_name(self, tmp_path):
        run_convert(FIXTURES / "tool-heavy-skill", tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "devops" in content.lower()

    def test_settings_json_has_permissions(self, tmp_path):
        run_convert(FIXTURES / "tool-heavy-skill", tmp_path)
        data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert "permissions" in data


class TestCLIConvertPregnancy:
    def test_exit_code_zero(self, tmp_path):
        result = run_convert(FIXTURES / "pregnancy-companion", tmp_path)
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_claude_md_contains_skill_name(self, tmp_path):
        run_convert(FIXTURES / "pregnancy-companion", tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "pregnancy" in content.lower()


class TestCLIErrors:
    def test_missing_source_nonzero_exit(self, tmp_path):
        result = run_convert(Path("/nonexistent/path"), tmp_path)
        assert result.returncode != 0

    def test_unknown_from_platform(self, tmp_path):
        cmd = [
            *AGENTSHIFT,
            "convert",
            str(FIXTURES / "simple-skill"),
            "--from",
            "badplatform",
            "--to",
            "claude-code",
            "--output",
            str(tmp_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode != 0

    def test_unknown_to_platform(self, tmp_path):
        cmd = [
            *AGENTSHIFT,
            "convert",
            str(FIXTURES / "simple-skill"),
            "--from",
            "openclaw",
            "--to",
            "badplatform",
            "--output",
            str(tmp_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode != 0

    def test_stdout_contains_skill_name(self, tmp_path):
        result = run_convert(FIXTURES / "simple-skill", tmp_path)
        assert "weather" in result.stdout.lower()
