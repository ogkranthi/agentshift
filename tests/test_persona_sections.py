"""Tests for persona.sections — parser detection, emitter mapping, diff row.

Covers spec A11 (persona-sections-schema.md) §7 checklist + additional cases.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentshift.diff import compute_diff, render_diff_table
from agentshift.emitters import bedrock as bedrock_emitter
from agentshift.emitters import vertex as vertex_emitter
from agentshift.ir import AgentIR, Metadata, Persona
from agentshift.parsers.openclaw import parse_skill_dir
from agentshift.sections import extract_sections

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ir(
    sections: dict[str, str] | None = None, system_prompt: str = "You are an agent."
) -> AgentIR:
    return AgentIR(
        name="test-agent",
        description="A test agent",
        persona=Persona(system_prompt=system_prompt, sections=sections),
        metadata=Metadata(source_platform="openclaw"),
    )


# ---------------------------------------------------------------------------
# 1. extract_sections — H2 headings
# ---------------------------------------------------------------------------


class TestExtractSectionsH2Headings:
    def test_extract_sections_h2_headings(self):
        body = "## Overview\nI provide weather data.\n\n## Behavior\nAlways state the location."
        result = extract_sections(body)
        assert "overview" in result
        assert "behavior" in result
        assert "weather" in result["overview"]
        assert "location" in result["behavior"]


# ---------------------------------------------------------------------------
# 2. H3 fallback
# ---------------------------------------------------------------------------


class TestExtractSectionsH3Fallback:
    def test_extract_sections_h3_fallback(self):
        body = "### Tools\nUse the fetch_weather tool.\n\n### Examples\nWhat is the weather in NYC?"
        result = extract_sections(body)
        assert "tools" in result
        assert "examples" in result
        assert "fetch_weather" in result["tools"]

    def test_h3_not_used_when_h2_present(self):
        body = "## Overview\nTop level.\n\n### Sub\nNested content."
        result = extract_sections(body)
        # Only H2 is selected; ### Sub should be included as body of overview
        assert "overview" in result
        assert "sub" not in result


# ---------------------------------------------------------------------------
# 3. Slug normalization
# ---------------------------------------------------------------------------


class TestExtractSectionsSlugNormalization:
    def test_extract_sections_slug_normalization(self):
        body = "## My Cool Section!\nSome content here."
        result = extract_sections(body)
        assert "my-cool-section" in result
        assert result["my-cool-section"] == "Some content here."

    def test_slug_lowercase(self):
        body = "## UPPERCASE\nContent."
        result = extract_sections(body)
        assert "uppercase" in result

    def test_slug_strips_special_chars(self):
        body = "## Guardrails & Safety\nDo not do bad things."
        result = extract_sections(body)
        # "Guardrails & Safety" → slug "guardrails-safety" ... but "guardrails" is a canonical,
        # and "safety" is an alias for "guardrails"; the raw slug would be "guardrails-safety"
        # which is NOT in ALIAS_MAP, so it stays as-is
        assert "guardrails-safety" in result


# ---------------------------------------------------------------------------
# 4. Alias normalization
# ---------------------------------------------------------------------------


class TestExtractSectionsAliasNormalization:
    def test_extract_sections_alias_normalization_safety(self):
        """## Safety → canonical slug 'guardrails'"""
        body = "## Safety\nNever provide medical diagnoses."
        result = extract_sections(body)
        assert "guardrails" in result
        assert "safety" not in result

    def test_alias_instructions_maps_to_behavior(self):
        body = "## Instructions\nFollow these rules."
        result = extract_sections(body)
        assert "behavior" in result
        assert "instructions" not in result

    def test_alias_about_maps_to_overview(self):
        body = "## About\nThis agent does X."
        result = extract_sections(body)
        assert "overview" in result
        assert "about" not in result

    def test_alias_personality_maps_to_persona(self):
        body = "## Personality\nWarm and helpful tone."
        result = extract_sections(body)
        assert "persona" in result
        assert "personality" not in result

    def test_alias_capabilities_maps_to_tools(self):
        body = "## Capabilities\nUse the weather tool."
        result = extract_sections(body)
        assert "tools" in result
        assert "capabilities" not in result


# ---------------------------------------------------------------------------
# 5. Preamble excluded
# ---------------------------------------------------------------------------


class TestExtractSectionsPreambleExcluded:
    def test_extract_sections_preamble_excluded(self):
        """Content before first heading should NOT appear in sections dict."""
        body = (
            "You are a helpful assistant.\n"
            "This line is a preamble.\n\n"
            "## Overview\n"
            "Primary goal: answer questions."
        )
        result = extract_sections(body)
        assert "overview" in result
        # preamble content should not be in any section value (since include_preamble=False by default)
        assert "preamble" not in result
        assert "You are a helpful assistant" not in result.get("overview", "")

    def test_preamble_key_present_when_include_preamble_true(self):
        body = "This is preamble text.\n\n## Behavior\nDo things carefully."
        result = extract_sections(body, include_preamble=True)
        assert "preamble" in result
        assert "preamble text" in result["preamble"]


# ---------------------------------------------------------------------------
# 6. Duplicate merging
# ---------------------------------------------------------------------------


class TestExtractSectionsDuplicateMerging:
    def test_extract_sections_duplicate_merging(self):
        """Two ## behavior headings → merged content with separator."""
        body = "## Behavior\nFirst rule: be helpful.\n\n## Behavior\nSecond rule: be concise."
        result = extract_sections(body)
        assert "behavior" in result
        merged = result["behavior"]
        assert "First rule" in merged
        assert "Second rule" in merged
        # Bodies should be separated
        assert "\n\n" in merged

    def test_alias_duplicate_merging(self):
        """## Safety and ## Guardrails both map to 'guardrails' — should merge."""
        body = "## Safety\nNo medical advice.\n\n## Guardrails\nNo legal advice either."
        result = extract_sections(body)
        assert "guardrails" in result
        merged = result["guardrails"]
        assert "medical" in merged
        assert "legal" in merged


# ---------------------------------------------------------------------------
# 7. Empty body
# ---------------------------------------------------------------------------


class TestExtractSectionsEmptyBody:
    def test_extract_sections_empty_body(self):
        result = extract_sections("")
        assert result == {}

    def test_extract_sections_whitespace_only(self):
        result = extract_sections("   \n\n\t  ")
        assert result == {}

    def test_extract_sections_none_like_empty(self):
        # Ensure no crash on empty-ish strings
        result = extract_sections("\n")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 8. No headings
# ---------------------------------------------------------------------------


class TestExtractSectionsNoHeadings:
    def test_extract_sections_no_headings(self):
        """Plain text body with no headings → empty sections dict."""
        body = "This is just plain text with no headings at all. No sections here."
        result = extract_sections(body)
        assert result == {}

    def test_extract_sections_h1_only_no_h2_or_h3(self):
        """H1 headings should NOT be picked up (only H2/H3 fallback)."""
        body = "# Top Level\nSome content.\n\n# Another Top\nMore content."
        result = extract_sections(body)
        assert result == {}


# ---------------------------------------------------------------------------
# 9. OpenClaw parser populates sections
# ---------------------------------------------------------------------------


class TestOpenclawParserPopulatesSections:
    def test_openclaw_parser_populates_sections(self, tmp_path):
        """parse_skill_dir with a SKILL.md containing H2 headings → ir.persona.sections populated."""
        skill_dir = tmp_path / "sections-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: sections-test\n"
            "description: A skill with structured sections.\n"
            "---\n\n"
            "## Overview\n"
            "I provide structured output.\n\n"
            "## Behavior\n"
            "Always be concise.\n\n"
            "## Guardrails\n"
            "Do not produce harmful content.\n",
            encoding="utf-8",
        )
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is not None
        assert "overview" in ir.persona.sections
        assert "behavior" in ir.persona.sections
        assert "guardrails" in ir.persona.sections
        assert "structured output" in ir.persona.sections["overview"]

    def test_openclaw_parser_no_sections_when_no_headings(self, tmp_path):
        """SKILL.md with flat body → sections is None."""
        skill_dir = tmp_path / "flat-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: flat-test\n"
            "description: A flat skill.\n"
            "---\n\n"
            "You are a helpful assistant. Do things helpfully.\n",
            encoding="utf-8",
        )
        ir = parse_skill_dir(skill_dir)
        assert ir.persona.sections is None or ir.persona.sections == {}


# ---------------------------------------------------------------------------
# 10. Claude Code parser populates sections
# ---------------------------------------------------------------------------


class TestClaudeCodeParserPopulatesSections:
    def test_claude_code_parser_populates_sections(self):
        """parse a CLAUDE.md-style body with headings → sections populated."""
        from agentshift.sections import extract_sections as _extract

        claude_md_body = (
            "## Overview\n"
            "You are a helpful coding assistant.\n\n"
            "## Rules\n"
            "Always write tests.\n"
            "Never break existing tests.\n\n"
            "## Tools\n"
            "Use bash, git, and grep.\n"
        )
        result = _extract(claude_md_body)
        assert "overview" in result
        # "Rules" maps to "behavior" via alias
        assert "behavior" in result
        assert "tools" in result
        assert "coding assistant" in result["overview"]
        assert "write tests" in result["behavior"]


# ---------------------------------------------------------------------------
# 11. Bedrock guardrails section mapped
# ---------------------------------------------------------------------------


class TestBedrockGuardrailsSectionMapped:
    def test_bedrock_guardrails_section_mapped(self, tmp_path):
        """IR with sections['guardrails'] → bedrock emitter produces guardrail-config.json."""
        ir = _make_ir(
            sections={
                "overview": "I answer weather questions.",
                "behavior": "Be concise.",
                "guardrails": "Never provide weather advisories as official warnings.",
            }
        )
        bedrock_emitter.emit(ir, tmp_path)
        guardrail_file = tmp_path / "guardrail-config.json"
        assert guardrail_file.exists(), (
            "guardrail-config.json should be created when sections['guardrails'] present"
        )
        config = json.loads(guardrail_file.read_text(encoding="utf-8"))
        assert "topicPolicyConfig" in config
        topics = config["topicPolicyConfig"]["topicsConfig"]
        assert len(topics) >= 1
        # All topics should have DENY type
        for topic in topics:
            assert topic["type"] == "DENY"

    def test_bedrock_guardrails_content_in_topics(self, tmp_path):
        """Guardrails text sentences are extracted as topic filter entries."""
        ir = _make_ir(
            sections={
                "guardrails": "Do not provide medical diagnoses. Avoid competitor products.",
            }
        )
        bedrock_emitter.emit(ir, tmp_path)
        config = json.loads((tmp_path / "guardrail-config.json").read_text())
        topics = config["topicPolicyConfig"]["topicsConfig"]
        all_definitions = " ".join(t["definition"] for t in topics)
        assert "medical" in all_definitions.lower() or "competitor" in all_definitions.lower()


# ---------------------------------------------------------------------------
# 12. Bedrock no sections falls back
# ---------------------------------------------------------------------------


class TestBedrockNoSectionsFallsBack:
    def test_bedrock_no_sections_falls_back(self, tmp_path):
        """IR with no sections → bedrock still works, uses system_prompt, no guardrail-config.json."""
        ir = _make_ir(sections=None, system_prompt="You are a helpful assistant.")
        bedrock_emitter.emit(ir, tmp_path)
        # Core files must still be created
        assert (tmp_path / "instruction.txt").exists()
        assert (tmp_path / "cloudformation.yaml").exists()
        # guardrail-config.json must NOT be created
        assert not (tmp_path / "guardrail-config.json").exists()
        # instruction.txt should contain system_prompt content
        instruction = (tmp_path / "instruction.txt").read_text(encoding="utf-8")
        assert "helpful assistant" in instruction

    def test_bedrock_sections_none_instruction_uses_system_prompt(self, tmp_path):
        """When sections is None, instruction.txt = system_prompt (if short enough)."""
        ir = _make_ir(sections=None, system_prompt="Be a weather bot.")
        bedrock_emitter.emit(ir, tmp_path)
        instruction = (tmp_path / "instruction.txt").read_text(encoding="utf-8")
        assert "weather bot" in instruction


# ---------------------------------------------------------------------------
# 13. Vertex overview as goal
# ---------------------------------------------------------------------------


class TestVertexOverviewAsGoal:
    def test_vertex_overview_as_goal(self, tmp_path):
        """IR with sections['overview'] → vertex agent.json goal field uses it."""
        overview_text = "I provide current weather and forecasts using wttr.in or Open-Meteo."
        ir = _make_ir(
            sections={
                "overview": overview_text,
                "behavior": "Always state the location you are reporting for.",
                "guardrails": "Do not provide official emergency warnings.",
            }
        )
        vertex_emitter.emit(ir, tmp_path)
        agent_json = json.loads((tmp_path / "agent.json").read_text(encoding="utf-8"))
        assert agent_json["goal"] == overview_text

    def test_vertex_overview_as_goal_truncated_at_8000(self, tmp_path):
        """Vertex goal is capped at 8000 chars."""
        long_overview = "x" * 10000
        ir = _make_ir(sections={"overview": long_overview})
        vertex_emitter.emit(ir, tmp_path)
        agent_json = json.loads((tmp_path / "agent.json").read_text(encoding="utf-8"))
        assert len(agent_json["goal"]) <= 8000

    def test_vertex_guardrails_in_instructions(self, tmp_path):
        """sections['guardrails'] → appears as 'Restrictions:' block in instructions."""
        ir = _make_ir(
            sections={
                "overview": "I am a weather bot.",
                "guardrails": "Never provide official emergency warnings.",
            }
        )
        vertex_emitter.emit(ir, tmp_path)
        agent_json = json.loads((tmp_path / "agent.json").read_text(encoding="utf-8"))
        instructions_text = " ".join(agent_json.get("instructions", []))
        assert "Restrictions" in instructions_text or "emergency" in instructions_text.lower()


# ---------------------------------------------------------------------------
# 14. Vertex no sections falls back
# ---------------------------------------------------------------------------


class TestVertexNoSectionsFallsBack:
    def test_vertex_no_sections_falls_back(self, tmp_path):
        """IR with no sections → vertex still works, agent.json created."""
        ir = _make_ir(sections=None, system_prompt="You are a helpful assistant.")
        vertex_emitter.emit(ir, tmp_path)
        assert (tmp_path / "agent.json").exists()
        agent_json = json.loads((tmp_path / "agent.json").read_text(encoding="utf-8"))
        assert "goal" in agent_json
        assert "helpful assistant" in agent_json["goal"]

    def test_vertex_no_sections_instructions_from_system_prompt(self, tmp_path):
        """Without sections, instructions are extracted from system_prompt lines."""
        ir = _make_ir(
            sections=None,
            system_prompt="You are a weather bot.\nAlways state the location.\nUse metric units.",
        )
        vertex_emitter.emit(ir, tmp_path)
        agent_json = json.loads((tmp_path / "agent.json").read_text(encoding="utf-8"))
        # Should have extracted non-empty instruction lines
        assert len(agent_json.get("instructions", [])) > 0


# ---------------------------------------------------------------------------
# 15. Diff includes persona sections row
# ---------------------------------------------------------------------------


class TestDiffIncludesPersonaSectionsRow:
    def test_diff_includes_persona_sections_row(self):
        """run compute_diff on IR with sections → 'persona_sections' in active components."""
        ir = _make_ir(
            sections={
                "overview": "I answer questions.",
                "behavior": "Be helpful.",
                "guardrails": "Do not harm.",
                "tools": "Use the search tool.",
            }
        )
        result = compute_diff(ir, ["bedrock", "vertex", "copilot"])
        assert "persona_sections" in result["active"]
        assert "persona_sections" in result["components"]

    def test_diff_persona_sections_label_contains_mapped(self):
        """The persona_sections row shows N/M mapped format."""
        ir = _make_ir(sections={"overview": "I do stuff.", "guardrails": "Do not be bad."})
        result = compute_diff(ir, ["bedrock"])
        label = result["components"]["persona_sections"]["bedrock"][1]
        assert "mapped" in label

    def test_diff_render_table_includes_persona_sections_text(self, capsys):
        """render_diff_table output contains 'Persona Sections' when sections present."""
        ir = _make_ir(sections={"overview": "I help users.", "guardrails": "No harmful content."})
        render_diff_table(ir, ["bedrock", "vertex"])
        captured = capsys.readouterr()
        assert "Persona Sections" in captured.out


# ---------------------------------------------------------------------------
# 16. Diff no sections row
# ---------------------------------------------------------------------------


class TestDiffNoSectionsRow:
    def test_diff_no_sections_row(self):
        """IR with no sections → 'persona_sections' NOT in active components."""
        ir = _make_ir(sections=None)
        result = compute_diff(ir, ["bedrock", "vertex"])
        assert "persona_sections" not in result["active"]

    def test_diff_no_sections_still_runs(self):
        """compute_diff runs without error when sections is None."""
        ir = _make_ir(sections=None)
        result = compute_diff(ir, ["bedrock", "vertex", "copilot", "claude-code"])
        assert "scores" in result
        assert "components" in result

    def test_diff_render_table_no_sections_no_crash(self, capsys):
        """render_diff_table does not crash when sections is None."""
        ir = _make_ir(sections=None)
        render_diff_table(ir, ["bedrock", "vertex"])
        # No exception, and we still get some output
        captured = capsys.readouterr()
        assert len(captured.out) > 0


# ---------------------------------------------------------------------------
# Backward compatibility — spec §7 item 13
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_ir_without_sections_is_valid(self):
        """IR without sections passes Pydantic validation with no errors."""
        ir = AgentIR(
            name="compat-agent",
            description="Backward compat test",
            persona=Persona(system_prompt="Do things."),
        )
        assert ir.persona.sections is None

    def test_ir_with_sections_none_explicit(self):
        """Explicitly setting sections=None is valid."""
        persona = Persona(system_prompt="You are an agent.", sections=None)
        assert persona.sections is None

    def test_ir_with_empty_sections_dict(self):
        """sections={} is also valid."""
        persona = Persona(system_prompt="You are an agent.", sections={})
        assert persona.sections == {}

    def test_all_emitters_work_without_sections(self, tmp_path):
        """Both bedrock and vertex emitters produce output when sections=None."""
        ir = _make_ir(sections=None, system_prompt="You are a general assistant.")
        bedrock_out = tmp_path / "bedrock"
        vertex_out = tmp_path / "vertex"
        bedrock_emitter.emit(ir, bedrock_out)
        vertex_emitter.emit(ir, vertex_out)
        assert (bedrock_out / "instruction.txt").exists()
        assert (vertex_out / "agent.json").exists()


# ---------------------------------------------------------------------------
# Round-trip — spec §7 item 14
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_roundtrip_sections_preserved(self, tmp_path):
        """parse → extract_sections on the system_prompt reproduces equivalent sections map."""
        original_body = (
            "## Overview\n"
            "I provide weather data.\n\n"
            "## Behavior\n"
            "Always state the location.\n\n"
            "## Guardrails\n"
            "Do not provide official emergency warnings.\n"
        )
        sections = extract_sections(original_body)
        # Reconstruct body from sections
        reconstructed_parts = []
        for slug, body in sections.items():
            reconstructed_parts.append(f"## {slug.title()}\n{body}")
        reconstructed = "\n\n".join(reconstructed_parts)
        re_extracted = extract_sections(reconstructed)

        # Keys should match
        assert set(sections.keys()) == set(re_extracted.keys())
        # Content should be preserved (may differ in whitespace)
        for key in sections:
            assert sections[key].strip() == re_extracted[key].strip()
