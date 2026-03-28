"""Unit tests for agentshift.sections — extract_sections() and normalize_slug()."""

from __future__ import annotations

from agentshift.sections import extract_sections, normalize_slug

# ---------------------------------------------------------------------------
# normalize_slug
# ---------------------------------------------------------------------------


class TestNormalizeSlug:
    def test_simple_lowercase(self):
        assert normalize_slug("Overview") == "overview"

    def test_already_lowercase(self):
        assert normalize_slug("overview") == "overview"

    def test_all_caps(self):
        assert normalize_slug("OVERVIEW") == "overview"

    def test_mixed_case_with_spaces(self):
        assert normalize_slug("How I Work") == "behavior"  # alias

    def test_hashes_stripped(self):
        assert normalize_slug("## Overview") == "overview"

    def test_triple_hashes_stripped(self):
        assert normalize_slug("### Instructions") == "behavior"

    def test_special_chars_become_hyphens(self):
        slug = normalize_slug("My Custom Section!")
        assert slug == "my-custom-section"

    def test_leading_trailing_hyphens_stripped(self):
        slug = normalize_slug("---My Section---")
        assert slug == "my-section"

    def test_alias_description_to_overview(self):
        assert normalize_slug("Description") == "overview"

    def test_alias_intro_to_overview(self):
        assert normalize_slug("intro") == "overview"

    def test_alias_introduction_to_overview(self):
        assert normalize_slug("Introduction") == "overview"

    def test_alias_about_to_overview(self):
        assert normalize_slug("about") == "overview"

    def test_alias_instructions_to_behavior(self):
        assert normalize_slug("Instructions") == "behavior"

    def test_alias_rules_to_behavior(self):
        assert normalize_slug("Rules") == "behavior"

    def test_alias_guidelines_to_behavior(self):
        assert normalize_slug("Guidelines") == "behavior"

    def test_alias_safety_to_guardrails(self):
        assert normalize_slug("Safety") == "guardrails"

    def test_alias_restrictions_to_guardrails(self):
        assert normalize_slug("Restrictions") == "guardrails"

    def test_alias_constraints_to_guardrails(self):
        assert normalize_slug("Constraints") == "guardrails"

    def test_alias_capabilities_to_tools(self):
        assert normalize_slug("Capabilities") == "tools"

    def test_alias_context_to_knowledge(self):
        assert normalize_slug("Context") == "knowledge"

    def test_alias_background_to_knowledge(self):
        assert normalize_slug("Background") == "knowledge"

    def test_alias_personality_to_persona(self):
        assert normalize_slug("Personality") == "persona"

    def test_alias_tone_to_persona(self):
        assert normalize_slug("Tone") == "persona"

    def test_alias_voice_to_persona(self):
        assert normalize_slug("Voice") == "persona"

    def test_alias_format_to_output_format(self):
        assert normalize_slug("Format") == "output-format"

    def test_alias_output_to_output_format(self):
        assert normalize_slug("Output") == "output-format"

    def test_unknown_heading_returns_slug(self):
        assert normalize_slug("My Fancy Custom Section") == "my-fancy-custom-section"

    def test_numeric_heading(self):
        slug = normalize_slug("Section 1")
        assert slug == "section-1"

    def test_heading_with_emoji_stripped(self):
        # Emojis become non-alphanumeric; should be stripped/converted
        slug = normalize_slug("Overview")
        assert slug == "overview"

    def test_multiword_alias_how_to_use(self):
        assert normalize_slug("How To Use") == "behavior"

    def test_alias_do_not_to_guardrails(self):
        assert normalize_slug("Do Not") == "guardrails"


# ---------------------------------------------------------------------------
# extract_sections — empty / no headings
# ---------------------------------------------------------------------------


class TestExtractSectionsEmpty:
    def test_empty_string_returns_empty_dict(self):
        assert extract_sections("") == {}

    def test_whitespace_only_returns_empty_dict(self):
        assert extract_sections("   \n\n  ") == {}

    def test_no_headings_returns_empty_dict(self):
        text = "This is a paragraph.\n\nAnother paragraph.\n"
        assert extract_sections(text) == {}

    def test_only_h1_returns_empty_dict(self):
        text = "# Title\n\nSome content here."
        assert extract_sections(text) == {}

    def test_none_like_input(self):
        # empty text
        assert extract_sections("") == {}


# ---------------------------------------------------------------------------
# extract_sections — H2 headings
# ---------------------------------------------------------------------------


class TestExtractSectionsH2:
    def test_single_h2_section(self):
        text = "## Overview\n\nThis is the overview.\n"
        result = extract_sections(text)
        assert "overview" in result
        assert result["overview"] == "This is the overview."

    def test_multiple_h2_sections(self):
        text = (
            "## Overview\n\nIntro content.\n\n"
            "## Behavior\n\nBehavior rules.\n\n"
            "## Tools\n\nTool list."
        )
        result = extract_sections(text)
        assert set(result.keys()) == {"overview", "behavior", "tools"}
        assert result["overview"] == "Intro content."
        assert result["behavior"] == "Behavior rules."
        assert result["tools"] == "Tool list."

    def test_h2_body_strips_whitespace(self):
        text = "## Overview\n\n  \n  Padded content.  \n  \n"
        result = extract_sections(text)
        assert result["overview"] == "Padded content."

    def test_h2_heading_aliases_normalized(self):
        text = "## Instructions\n\nDo this.\n"
        result = extract_sections(text)
        assert "behavior" in result
        assert result["behavior"] == "Do this."

    def test_h2_heading_case_insensitive(self):
        text = "## OVERVIEW\n\nContent A.\n\n## overview\n\nContent B.\n"
        result = extract_sections(text)
        # Both should map to "overview" and be merged
        assert "overview" in result
        # Merged content
        assert "Content A." in result["overview"]
        assert "Content B." in result["overview"]

    def test_h2_duplicate_slugs_merged(self):
        text = "## About\n\nFirst.\n\n## Description\n\nSecond.\n"
        result = extract_sections(text)
        # Both "About" and "Description" map to "overview"
        assert "overview" in result
        assert "First." in result["overview"]
        assert "Second." in result["overview"]

    def test_preamble_excluded_by_default(self):
        text = "Preamble content here.\n\n## Overview\n\nSection content."
        result = extract_sections(text)
        assert "preamble" not in result
        assert result["overview"] == "Section content."

    def test_preamble_included_when_flag_set(self):
        text = "Preamble content.\n\n## Overview\n\nSection content."
        result = extract_sections(text, include_preamble=True)
        assert "preamble" in result
        assert result["preamble"] == "Preamble content."

    def test_h2_preferred_over_h3(self):
        text = "## Top Level\n\nH2 content.\n\n### Sub Section\n\nH3 content."
        result = extract_sections(text)
        assert "top-level" in result
        # H3 body is part of top level's body, not a separate key
        assert "sub-section" not in result

    def test_no_alias_normalize_disabled(self):
        text = "## Instructions\n\nDo this.\n"
        result = extract_sections(text, normalize_aliases=False)
        assert "instructions" in result
        assert "behavior" not in result


# ---------------------------------------------------------------------------
# extract_sections — H3 fallback
# ---------------------------------------------------------------------------


class TestExtractSectionsH3Fallback:
    def test_h3_used_when_no_h2(self):
        text = "### Overview\n\nH3 content.\n"
        result = extract_sections(text)
        assert "overview" in result
        assert result["overview"] == "H3 content."

    def test_h3_multiple_sections(self):
        text = "### Overview\n\nIntro.\n\n### Behavior\n\nRules.\n\n### Guardrails\n\nSafety rules."
        result = extract_sections(text)
        assert set(result.keys()) == {"overview", "behavior", "guardrails"}

    def test_h3_alias_normalized(self):
        text = "### About\n\nSome content.\n"
        result = extract_sections(text)
        assert result.get("overview") == "Some content."


# ---------------------------------------------------------------------------
# extract_sections — multiline bodies
# ---------------------------------------------------------------------------


class TestExtractSectionsMultiline:
    def test_multiline_body_preserved(self):
        text = "## Overview\n\nLine 1.\nLine 2.\nLine 3.\n"
        result = extract_sections(text)
        body = result["overview"]
        assert "Line 1." in body
        assert "Line 2." in body
        assert "Line 3." in body

    def test_body_with_code_block(self):
        text = "## Tools\n\n```bash\necho hello\n```\n"
        result = extract_sections(text)
        assert "```bash" in result["tools"]

    def test_body_with_nested_h3_not_parsed(self):
        text = "## Overview\n\nIntro text.\n\n### Sub-section\n\nSub content.\n"
        result = extract_sections(text)
        assert "overview" in result
        # H3 inside H2 section is treated as body text, not a separate section
        assert "sub-section" not in result
        assert "Sub content." in result["overview"]


# ---------------------------------------------------------------------------
# extract_sections — guardrails key
# ---------------------------------------------------------------------------


class TestExtractSectionsGuardrails:
    def test_safety_heading_maps_to_guardrails(self):
        text = "## Safety\n\nDo not do X.\nDo not do Y.\n"
        result = extract_sections(text)
        assert "guardrails" in result

    def test_restrictions_heading_maps_to_guardrails(self):
        text = "## Restrictions\n\nNo personal data.\n"
        result = extract_sections(text)
        assert "guardrails" in result

    def test_guardrails_body_content(self):
        text = "## Guardrails\n\nNever reveal secrets.\n"
        result = extract_sections(text)
        assert result["guardrails"] == "Never reveal secrets."
