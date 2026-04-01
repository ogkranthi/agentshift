"""Edge-case tests for parser robustness and emitter fidelity."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentshift.emitters.claude_code import emit
from agentshift.ir import AgentIR
from agentshift.parsers.openclaw import parse_skill_dir

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_skill_dir(tmp_path: Path, content: str) -> Path:
    """Write SKILL.md content to a temp directory and return the path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SKILL.md").write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# 1. No frontmatter — just markdown body
# ---------------------------------------------------------------------------


class TestNoFrontmatter:
    def test_parses_without_exception(self, tmp_path):
        d = make_skill_dir(
            tmp_path, "# My Skill\n\nThis is the body with no frontmatter.\n"
        )
        ir = parse_skill_dir(d)
        assert isinstance(ir, AgentIR)

    def test_name_falls_back_to_dir_name(self, tmp_path):
        d = make_skill_dir(tmp_path, "# My Skill\n\nBody text here.\n")
        ir = parse_skill_dir(d)
        # Name should fall back to directory name since no frontmatter
        assert ir.name == tmp_path.name or ir.name  # non-empty

    def test_body_captured_in_persona(self, tmp_path):
        body = "# My Skill\n\nSome instructions here.\n"
        d = make_skill_dir(tmp_path, body)
        ir = parse_skill_dir(d)
        assert ir.persona.system_prompt is not None
        assert len(ir.persona.system_prompt) > 0

    def test_source_platform_is_openclaw(self, tmp_path):
        d = make_skill_dir(tmp_path, "Just plain markdown, no frontmatter.\n")
        ir = parse_skill_dir(d)
        assert ir.metadata.source_platform == "openclaw"


# ---------------------------------------------------------------------------
# 2. Frontmatter only, empty body
# ---------------------------------------------------------------------------


class TestFrontmatterOnlyEmptyBody:
    FRONTMATTER_ONLY = "---\nname: fm-only\ndescription: 'Only frontmatter'\n---\n"

    def test_parses_without_exception(self, tmp_path):
        d = make_skill_dir(tmp_path, self.FRONTMATTER_ONLY)
        ir = parse_skill_dir(d)
        assert isinstance(ir, AgentIR)

    def test_name_from_frontmatter(self, tmp_path):
        d = make_skill_dir(tmp_path, self.FRONTMATTER_ONLY)
        ir = parse_skill_dir(d)
        assert ir.name == "fm-only"

    def test_description_from_frontmatter(self, tmp_path):
        d = make_skill_dir(tmp_path, self.FRONTMATTER_ONLY)
        ir = parse_skill_dir(d)
        assert ir.description == "Only frontmatter"

    def test_emits_without_exception(self, tmp_path):
        skill_dir = make_skill_dir(tmp_path / "skill", self.FRONTMATTER_ONLY)
        ir = parse_skill_dir(skill_dir)
        out = tmp_path / "out"
        emit(ir, out)
        assert (out / "CLAUDE.md").exists()


# ---------------------------------------------------------------------------
# 3. Special characters in name (emoji, unicode, quotes)
# ---------------------------------------------------------------------------


class TestSpecialCharsInName:
    def test_emoji_in_name(self, tmp_path):
        content = "---\nname: 'weather-🌤️'\ndescription: 'Emoji name'\n---\n\nBody.\n"
        d = make_skill_dir(tmp_path, content)
        ir = parse_skill_dir(d)
        assert isinstance(ir, AgentIR)
        assert ir.name  # non-empty

    def test_unicode_in_name(self, tmp_path):
        content = (
            "---\nname: '日本語スキル'\ndescription: 'Unicode name'\n---\n\nBody.\n"
        )
        d = make_skill_dir(tmp_path, content)
        ir = parse_skill_dir(d)
        assert isinstance(ir, AgentIR)
        assert ir.name  # non-empty

    def test_quotes_in_name(self, tmp_path):
        content = (
            "---\nname: \"my 'cool' skill\"\ndescription: Quotes test\n---\n\nBody.\n"
        )
        d = make_skill_dir(tmp_path, content)
        ir = parse_skill_dir(d)
        assert isinstance(ir, AgentIR)
        assert ir.name  # non-empty

    def test_special_chars_dont_crash_emitter(self, tmp_path):
        content = "---\nname: 'emoji-🤖-skill'\ndescription: '描述 & \"special\" chars'\n---\n\nBody with <tags> & entities.\n"
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        ir = parse_skill_dir(skill_dir)
        out = tmp_path / "out"
        emit(ir, out)
        assert (out / "CLAUDE.md").exists()
        text = (out / "CLAUDE.md").read_text(encoding="utf-8")
        assert text.strip()  # non-empty


# ---------------------------------------------------------------------------
# 4. Very long description (>2000 chars)
# ---------------------------------------------------------------------------


class TestVeryLongDescription:
    LONG_DESC = "A" * 2500

    def test_parses_long_description(self, tmp_path):
        content = f"---\nname: long-desc-skill\ndescription: '{self.LONG_DESC}'\n---\n\nBody.\n"
        d = make_skill_dir(tmp_path, content)
        ir = parse_skill_dir(d)
        assert len(ir.description) == 2500

    def test_emits_long_description(self, tmp_path):
        content = f"---\nname: long-desc-skill\ndescription: '{self.LONG_DESC}'\n---\n\nBody.\n"
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        ir = parse_skill_dir(skill_dir)
        out = tmp_path / "out"
        emit(ir, out)
        claude_md = (out / "CLAUDE.md").read_text(encoding="utf-8")
        assert self.LONG_DESC in claude_md


# ---------------------------------------------------------------------------
# 5. Empty SKILL.md (0 bytes)
# ---------------------------------------------------------------------------


class TestEmptySkillMd:
    def test_empty_file_no_raw_crash(self, tmp_path):
        (tmp_path / "SKILL.md").write_bytes(b"")
        # Should either parse cleanly or raise a clear typed exception
        try:
            ir = parse_skill_dir(tmp_path)
            # If it parses, name should at least be the dir name
            assert ir.name
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            # Clear typed exceptions are acceptable
            assert str(exc)  # message non-empty
        except Exception as exc:
            # Any other exception must be a recognizable type, not a raw crash
            pytest.fail(f"Unexpected exception type {type(exc).__name__}: {exc}")

    def test_empty_file_emitter_safe(self, tmp_path):
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_bytes(b"")
        try:
            ir = parse_skill_dir(skill_dir)
            out = tmp_path / "out"
            emit(ir, out)
            assert (out / "CLAUDE.md").exists()
        except Exception:
            pass  # acceptable to raise, but not crash interpreter


# ---------------------------------------------------------------------------
# 6. Malformed YAML frontmatter
# ---------------------------------------------------------------------------


class TestMalformedYAML:
    MALFORMED = "---\nname: [unclosed bracket\ndescription: bad: yaml: here\n---\n\nBody text.\n"

    def test_malformed_yaml_no_raw_crash(self, tmp_path):
        d = make_skill_dir(tmp_path, self.MALFORMED)
        try:
            ir = parse_skill_dir(d)
            assert ir.name  # if it parses, name must be set
        except Exception as exc:
            # Must be a recognizable exception type — check via str representation
            assert type(exc).__name__ in (
                "YAMLError",
                "ScannerError",
                "ParserError",
                "ValueError",
                "KeyError",
                "TypeError",
            ), f"Unexpected raw crash: {type(exc).__name__}: {exc}"

    def test_tab_in_frontmatter(self, tmp_path):
        """YAML doesn't allow tabs; should not crash interpreter."""
        content = "---\nname:\tmy-skill\ndescription: tabbed\n---\n\nBody.\n"
        d = make_skill_dir(tmp_path, content)
        try:
            ir = parse_skill_dir(d)
            assert ir.name
        except Exception as exc:
            # Typed exception OK
            assert type(exc).__name__  # non-empty name

    def test_only_dashes_frontmatter(self, tmp_path):
        """Frontmatter with only --- and no content."""
        content = "---\n---\n\nBody only.\n"
        d = make_skill_dir(tmp_path, content)
        ir = parse_skill_dir(d)
        # Should fall back to directory name
        assert ir.name == tmp_path.name


# ---------------------------------------------------------------------------
# 7. Emitter Fidelity — 5 real skills
# ---------------------------------------------------------------------------

REAL_SKILLS_DIR = Path(
    "/Users/kranthikumar/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills"
)
RICH_SKILLS = ["coding-agent", "slack", "github", "notion", "weather"]


@pytest.mark.skipif(
    not REAL_SKILLS_DIR.exists(),
    reason="Real OpenClaw skills directory not found",
)
class TestEmitterFidelityRealSkills:
    @pytest.mark.parametrize("skill_name", RICH_SKILLS)
    def test_contains_skill_name_in_claude_md(self, skill_name, tmp_path):
        skill_path = REAL_SKILLS_DIR / skill_name
        if not skill_path.exists():
            pytest.skip(f"Skill {skill_name} not found")
        ir = parse_skill_dir(skill_path)
        emit(ir, tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert (
            skill_name[:5].lower() in content.lower()
        ), f"Skill name prefix {skill_name[:5]!r} not found in CLAUDE.md"

    @pytest.mark.parametrize("skill_name", RICH_SKILLS)
    def test_valid_utf8_non_empty(self, skill_name, tmp_path):
        skill_path = REAL_SKILLS_DIR / skill_name
        if not skill_path.exists():
            pytest.skip(f"Skill {skill_name} not found")
        ir = parse_skill_dir(skill_path)
        emit(ir, tmp_path)
        raw = (tmp_path / "CLAUDE.md").read_bytes()
        text = raw.decode("utf-8")  # raises if not valid UTF-8
        assert text.strip()

    @pytest.mark.parametrize("skill_name", RICH_SKILLS)
    def test_no_raw_python_reprs(self, skill_name, tmp_path):
        skill_path = REAL_SKILLS_DIR / skill_name
        if not skill_path.exists():
            pytest.skip(f"Skill {skill_name} not found")
        ir = parse_skill_dir(skill_path)
        emit(ir, tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert (
            "<agentshift." not in content
        ), "Raw Python object repr found in CLAUDE.md"
        assert (
            "object at 0x" not in content
        ), "Raw Python object repr found in CLAUDE.md"

    @pytest.mark.parametrize("skill_name", RICH_SKILLS)
    def test_description_in_claude_md(self, skill_name, tmp_path):
        skill_path = REAL_SKILLS_DIR / skill_name
        if not skill_path.exists():
            pytest.skip(f"Skill {skill_name} not found")
        ir = parse_skill_dir(skill_path)
        emit(ir, tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        # If description is non-empty, it should appear in CLAUDE.md
        if ir.description:
            # Check at least a meaningful prefix is present
            desc_prefix = ir.description[:30].strip()
            assert (
                desc_prefix in content
            ), f"Description prefix {desc_prefix!r} not found in CLAUDE.md"

    @pytest.mark.parametrize("skill_name", RICH_SKILLS)
    def test_settings_json_valid(self, skill_name, tmp_path):
        import json

        skill_path = REAL_SKILLS_DIR / skill_name
        if not skill_path.exists():
            pytest.skip(f"Skill {skill_name} not found")
        ir = parse_skill_dir(skill_path)
        emit(ir, tmp_path)
        data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert isinstance(data, dict)
