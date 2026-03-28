"""Tests for persona.sections integration in agentshift.diff portability matrix."""

from __future__ import annotations

import pytest

from agentshift.diff import (
    FULL,
    NONE,
    PARTIAL,
    SECTION_PLATFORM_SUPPORT,
    _component_display,
    _count_mapped_sections,
    compute_diff,
)
from agentshift.ir import AgentIR, Persona


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ir(sections: dict[str, str] | None = None, system_prompt: str = "Do things.") -> AgentIR:
    return AgentIR(
        name="test-agent",
        description="A test agent.",
        persona=Persona(system_prompt=system_prompt, sections=sections),
    )


# ---------------------------------------------------------------------------
# _count_mapped_sections
# ---------------------------------------------------------------------------


class TestCountMappedSections:
    def test_all_known_sections_for_bedrock(self):
        sections = {"behavior": "B", "tools": "T", "knowledge": "K"}
        mapped, total = _count_mapped_sections(sections, "bedrock")
        assert total == 3
        assert mapped == 3

    def test_partial_mapping(self):
        # "examples" is only supported on claude-code and copilot, not bedrock
        sections = {"behavior": "B", "examples": "E"}
        mapped, total = _count_mapped_sections(sections, "bedrock")
        assert total == 2
        assert mapped == 1  # only "behavior" maps to bedrock

    def test_empty_sections(self):
        mapped, total = _count_mapped_sections({}, "bedrock")
        assert total == 0
        assert mapped == 0

    def test_overview_maps_to_vertex(self):
        sections = {"overview": "O"}
        mapped, total = _count_mapped_sections(sections, "vertex")
        assert mapped == 1
        assert total == 1

    def test_guardrails_maps_to_bedrock(self):
        sections = {"guardrails": "G"}
        mapped, total = _count_mapped_sections(sections, "bedrock")
        assert mapped == 1

    def test_unknown_section_maps_to_claude_code(self):
        sections = {"my-custom-section": "Content"}
        mapped, total = _count_mapped_sections(sections, "claude-code")
        # Unknown sections default to claude-code
        assert mapped == 1
        assert total == 1

    def test_unknown_section_does_not_map_to_bedrock(self):
        sections = {"my-custom-section": "Content"}
        mapped, total = _count_mapped_sections(sections, "bedrock")
        assert mapped == 0
        assert total == 1


# ---------------------------------------------------------------------------
# compute_diff — persona_sections component
# ---------------------------------------------------------------------------


class TestComputeDiffPersonaSections:
    def test_persona_sections_not_in_active_when_sections_none(self):
        ir = _make_ir(sections=None)
        result = compute_diff(ir, ["claude-code"])
        assert "persona_sections" not in result["active"]

    def test_persona_sections_in_active_when_sections_present(self):
        sections = {"overview": "Intro.", "behavior": "Be helpful."}
        ir = _make_ir(sections=sections)
        result = compute_diff(ir, ["claude-code"])
        assert "persona_sections" in result["active"]

    def test_persona_sections_full_when_all_mapped(self):
        # behavior maps to bedrock
        sections = {"behavior": "Follow rules."}
        ir = _make_ir(sections=sections)
        result = compute_diff(ir, ["bedrock"])
        comp_data = result["components"]["persona_sections"]["bedrock"]
        fidelity, label, note = comp_data
        assert fidelity == FULL
        assert "1/1" in label

    def test_persona_sections_none_fidelity_when_none_mapped(self):
        # "examples" does not map to bedrock
        sections = {"examples": "Example interactions."}
        ir = _make_ir(sections=sections)
        result = compute_diff(ir, ["bedrock"])
        comp_data = result["components"]["persona_sections"]["bedrock"]
        fidelity, label, note = comp_data
        assert fidelity == NONE
        assert "0/1" in label

    def test_persona_sections_partial_when_some_mapped(self):
        # behavior maps to bedrock, examples does not
        sections = {"behavior": "Rules.", "examples": "Demos."}
        ir = _make_ir(sections=sections)
        result = compute_diff(ir, ["bedrock"])
        comp_data = result["components"]["persona_sections"]["bedrock"]
        fidelity, label, note = comp_data
        assert fidelity == PARTIAL
        assert "1/2" in label

    def test_persona_sections_label_format(self):
        sections = {"overview": "O.", "behavior": "B.", "tools": "T."}
        ir = _make_ir(sections=sections)
        result = compute_diff(ir, ["claude-code"])
        comp_data = result["components"]["persona_sections"]["claude-code"]
        fidelity, label, note = comp_data
        # Label should include N/M format
        assert "/" in label
        assert "mapped" in label

    def test_persona_sections_empty_dict(self):
        """Empty sections dict: 0/0 label with NONE fidelity."""
        ir = _make_ir(sections={})
        # sections={} is falsy but not None — persona_sections won't be in active
        result = compute_diff(ir, ["claude-code"])
        # Empty dict is falsy, so persona_sections not added to active
        assert "persona_sections" not in result["active"]

    def test_persona_sections_note_is_none(self):
        sections = {"overview": "O."}
        ir = _make_ir(sections=sections)
        result = compute_diff(ir, ["claude-code"])
        comp_data = result["components"]["persona_sections"]["claude-code"]
        fidelity, label, note = comp_data
        assert note is None

    def test_persona_sections_multiple_targets(self):
        sections = {
            "overview": "Intro.",
            "behavior": "Rules.",
            "guardrails": "Restrictions.",
        }
        ir = _make_ir(sections=sections)
        targets = ["claude-code", "bedrock", "vertex"]
        result = compute_diff(ir, targets)
        assert "persona_sections" in result["active"]
        for target in targets:
            assert target in result["components"]["persona_sections"]


# ---------------------------------------------------------------------------
# _component_display — "Persona Sections" label
# ---------------------------------------------------------------------------


class TestComponentDisplay:
    def test_persona_sections_label_includes_count(self):
        sections = {"overview": "O.", "behavior": "B.", "tools": "T."}
        ir = _make_ir(sections=sections)
        label = _component_display("persona_sections", ir)
        assert "Persona Sections" in label
        assert "(3)" in label

    def test_persona_sections_label_zero_sections(self):
        ir = _make_ir(sections=None)
        label = _component_display("persona_sections", ir)
        assert "Persona Sections" in label
        assert "(0)" in label

    def test_persona_sections_label_one_section(self):
        ir = _make_ir(sections={"overview": "Just one."})
        label = _component_display("persona_sections", ir)
        assert "(1)" in label

    def test_other_components_not_affected(self):
        ir = _make_ir()
        label = _component_display("instructions", ir)
        assert "Persona Sections" not in label


# ---------------------------------------------------------------------------
# SECTION_PLATFORM_SUPPORT — spot checks
# ---------------------------------------------------------------------------


class TestSectionPlatformSupport:
    def test_overview_supported_on_vertex(self):
        assert "vertex" in SECTION_PLATFORM_SUPPORT["overview"]

    def test_behavior_supported_on_bedrock(self):
        assert "bedrock" in SECTION_PLATFORM_SUPPORT["behavior"]

    def test_guardrails_supported_on_bedrock(self):
        assert "bedrock" in SECTION_PLATFORM_SUPPORT["guardrails"]

    def test_examples_not_on_bedrock(self):
        assert "bedrock" not in SECTION_PLATFORM_SUPPORT["examples"]

    def test_auth_only_claude_code(self):
        assert SECTION_PLATFORM_SUPPORT["auth"] == {"claude-code"}
