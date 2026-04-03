"""T18 — A2A emitter tests.

Tests for A2A Agent Card emitter (src/agentshift/emitters/a2a.py):
- emit() writes agent-card.json with required A2A fields
- Required fields: name, description, version, supportedInterfaces, capabilities, skills
- Skills map from IR tools
- Edge case: IR with no tools → valid minimal A2A card
- Security schemes from tool auth
- Governance extension in capabilities
- README.md is generated
- Fixture conversion: parse pregnancy-companion → emit A2A → validate card
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentshift.emitters import a2a as a2a_emitter
from agentshift.ir import AgentIR, Governance, Guardrail, Persona, Tool, ToolAuth, Trigger
from agentshift.parsers.openclaw import parse_skill_dir as parse_openclaw

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PREGNANCY_COMPANION_DIR = FIXTURES_DIR / "pregnancy-companion"


def _make_ir(**kwargs) -> AgentIR:
    """Build a base AgentIR for A2A emitter tests."""
    defaults = dict(
        name="my-a2a-agent",
        description="An agent used for A2A emitter testing.",
        persona=Persona(system_prompt="You are a helpful test agent."),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


def _emit_and_load(ir: AgentIR, tmp_path: Path) -> dict:
    """Emit to tmp_path and load the resulting agent-card.json."""
    a2a_emitter.emit(ir, tmp_path)
    card_path = tmp_path / "agent-card.json"
    assert card_path.exists(), "agent-card.json was not created"
    return json.loads(card_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Required A2A fields
# ---------------------------------------------------------------------------


class TestRequiredFields:
    """Verify that all required A2A Agent Card fields are present."""

    def test_name_present(self, tmp_path):
        card = _emit_and_load(_make_ir(name="test-agent"), tmp_path)
        assert "name" in card
        assert card["name"] == "test-agent"

    def test_description_present(self, tmp_path):
        card = _emit_and_load(_make_ir(description="My test agent."), tmp_path)
        assert "description" in card
        assert "test agent" in card["description"].lower()

    def test_version_present(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "version" in card

    def test_version_defaults_to_1_0_0(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert card["version"] == "1.0.0"

    def test_supported_interfaces_present(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "supportedInterfaces" in card
        assert isinstance(card["supportedInterfaces"], list)
        assert len(card["supportedInterfaces"]) >= 1

    def test_supported_interfaces_has_url(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        iface = card["supportedInterfaces"][0]
        assert "url" in iface

    def test_supported_interfaces_has_protocol_binding(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        iface = card["supportedInterfaces"][0]
        assert "protocolBinding" in iface

    def test_capabilities_present(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "capabilities" in card
        assert isinstance(card["capabilities"], dict)

    def test_capabilities_has_streaming(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "streaming" in card["capabilities"]

    def test_capabilities_has_push_notifications(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "pushNotifications" in card["capabilities"]

    def test_skills_present(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "skills" in card
        assert isinstance(card["skills"], list)

    def test_default_input_modes_present(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "defaultInputModes" in card
        assert "text/plain" in card["defaultInputModes"]

    def test_default_output_modes_present(self, tmp_path):
        card = _emit_and_load(_make_ir(), tmp_path)
        assert "defaultOutputModes" in card
        assert "text/plain" in card["defaultOutputModes"]


# ---------------------------------------------------------------------------
# Skills from IR tools
# ---------------------------------------------------------------------------


class TestSkillsMapping:
    """Tests for mapping IR tools → A2A skills."""

    def test_tools_mapped_to_skills(self, tmp_path):
        ir = _make_ir(
            tools=[
                Tool(name="web_search", description="Search the web", kind="builtin"),
                Tool(name="bash", description="Run commands", kind="shell"),
            ]
        )
        card = _emit_and_load(ir, tmp_path)
        skill_ids = {s["id"] for s in card["skills"]}
        assert "web_search" in skill_ids
        assert "bash" in skill_ids

    def test_skill_has_required_fields(self, tmp_path):
        ir = _make_ir(tools=[Tool(name="my-tool", description="Does stuff", kind="function")])
        card = _emit_and_load(ir, tmp_path)
        skill = card["skills"][0]
        assert "id" in skill
        assert "name" in skill
        assert "description" in skill
        assert "tags" in skill

    def test_skill_description_from_tool(self, tmp_path):
        ir = _make_ir(
            tools=[Tool(name="calc", description="Calculate expressions", kind="function")]
        )
        card = _emit_and_load(ir, tmp_path)
        skill = card["skills"][0]
        assert "calculate" in skill["description"].lower()

    def test_skill_name_humanized(self, tmp_path):
        ir = _make_ir(tools=[Tool(name="web_search", description="Search", kind="builtin")])
        card = _emit_and_load(ir, tmp_path)
        # "web_search" → "Web Search" (title case)
        skill = card["skills"][0]
        assert skill["name"] == "Web Search"

    def test_skill_tags_include_kind(self, tmp_path):
        ir = _make_ir(tools=[Tool(name="bash", description="Run shell commands", kind="shell")])
        card = _emit_and_load(ir, tmp_path)
        skill = next(s for s in card["skills"] if s["id"] == "bash")
        assert "shell" in skill["tags"]

    def test_multiple_tools_produce_multiple_skills(self, tmp_path):
        ir = _make_ir(
            tools=[
                Tool(name="tool-a", description="Tool A", kind="function"),
                Tool(name="tool-b", description="Tool B", kind="function"),
                Tool(name="tool-c", description="Tool C", kind="mcp"),
            ]
        )
        card = _emit_and_load(ir, tmp_path)
        assert len(card["skills"]) == 3


# ---------------------------------------------------------------------------
# Edge case: IR with no tools → valid minimal A2A card
# ---------------------------------------------------------------------------


class TestNoToolsEdgeCase:
    """IR with no tools should produce a valid, minimal A2A card."""

    def test_no_tools_emits_valid_card(self, tmp_path):
        ir = _make_ir(tools=[])
        card = _emit_and_load(ir, tmp_path)
        assert isinstance(card, dict)

    def test_no_tools_has_at_least_one_skill(self, tmp_path):
        """A2A requires at least one skill — agent itself is used as fallback."""
        ir = _make_ir(name="minimal-agent", description="A minimal agent.", tools=[])
        card = _emit_and_load(ir, tmp_path)
        assert len(card["skills"]) >= 1

    def test_no_tools_fallback_skill_uses_agent_name(self, tmp_path):
        ir = _make_ir(name="minimal-agent", description="Minimal.", tools=[])
        card = _emit_and_load(ir, tmp_path)
        skill = card["skills"][0]
        assert skill["id"] == "minimal-agent"

    def test_no_tools_fallback_skill_description(self, tmp_path):
        ir = _make_ir(name="x", description="Does everything.", tools=[])
        card = _emit_and_load(ir, tmp_path)
        skill = card["skills"][0]
        assert "everything" in skill["description"].lower()

    def test_no_tools_required_fields_still_present(self, tmp_path):
        ir = _make_ir(tools=[])
        card = _emit_and_load(ir, tmp_path)
        for field in (
            "name",
            "description",
            "version",
            "supportedInterfaces",
            "capabilities",
            "skills",
        ):
            assert field in card, f"Required field {field!r} missing from minimal card"

    def test_no_tools_streaming_false(self, tmp_path):
        """No triggers → streaming and pushNotifications default to False."""
        ir = _make_ir(tools=[], triggers=[])
        card = _emit_and_load(ir, tmp_path)
        assert card["capabilities"]["streaming"] is False
        assert card["capabilities"]["pushNotifications"] is False


# ---------------------------------------------------------------------------
# Security schemes
# ---------------------------------------------------------------------------


class TestSecuritySchemes:
    """Tests for security scheme generation from tool auth."""

    def test_api_key_auth_produces_scheme(self, tmp_path):
        ir = _make_ir(
            tools=[
                Tool(
                    name="my-api",
                    description="Call my API",
                    kind="function",
                    auth=ToolAuth(type="api_key", env_var="MY_API_KEY"),
                )
            ]
        )
        card = _emit_and_load(ir, tmp_path)
        assert "securitySchemes" in card
        assert any("api_key" in k for k in card["securitySchemes"])

    def test_bearer_auth_produces_scheme(self, tmp_path):
        ir = _make_ir(
            tools=[
                Tool(
                    name="bearer-tool",
                    description="Bearer-authenticated tool",
                    kind="function",
                    auth=ToolAuth(type="bearer"),
                )
            ]
        )
        card = _emit_and_load(ir, tmp_path)
        assert "securitySchemes" in card
        scheme = next(iter(card["securitySchemes"].values()))
        assert "httpAuthSecurityScheme" in scheme

    def test_oauth2_auth_produces_scheme(self, tmp_path):
        ir = _make_ir(
            tools=[
                Tool(
                    name="oauth-tool",
                    description="OAuth2 tool",
                    kind="function",
                    auth=ToolAuth(type="oauth2", scopes=["read:data"]),
                )
            ]
        )
        card = _emit_and_load(ir, tmp_path)
        assert "securitySchemes" in card
        scheme = next(iter(card["securitySchemes"].values()))
        assert "oauth2SecurityScheme" in scheme

    def test_no_auth_no_security_schemes(self, tmp_path):
        ir = _make_ir(tools=[Tool(name="public-tool", description="Public", kind="function")])
        card = _emit_and_load(ir, tmp_path)
        assert "securitySchemes" not in card or not card.get("securitySchemes")

    def test_security_requirements_mirror_schemes(self, tmp_path):
        ir = _make_ir(
            tools=[
                Tool(
                    name="key-tool",
                    description="API key tool",
                    kind="function",
                    auth=ToolAuth(type="api_key", env_var="KEY"),
                )
            ]
        )
        card = _emit_and_load(ir, tmp_path)
        assert "securityRequirements" in card
        scheme_names = set(card["securitySchemes"].keys())
        req_names = {next(iter(req.keys())) for req in card["securityRequirements"]}
        assert scheme_names == req_names


# ---------------------------------------------------------------------------
# Governance extension in capabilities
# ---------------------------------------------------------------------------


class TestGovernanceExtension:
    """Tests for governance extension in capabilities."""

    def test_guardrails_produce_extension(self, tmp_path):
        ir = _make_ir(
            governance=Governance(
                guardrails=[
                    Guardrail(id="G001", text="Do not share PII.", category="privacy"),
                ]
            )
        )
        card = _emit_and_load(ir, tmp_path)
        caps = card["capabilities"]
        assert "extensions" in caps
        ext_uris = [e["uri"] for e in caps["extensions"]]
        assert any("governance" in uri for uri in ext_uris)

    def test_governance_extension_has_guardrail_count(self, tmp_path):
        ir = _make_ir(
            governance=Governance(
                guardrails=[
                    Guardrail(id="G001", text="Rule 1", category="safety"),
                    Guardrail(id="G002", text="Rule 2", category="ethical"),
                ]
            )
        )
        card = _emit_and_load(ir, tmp_path)
        ext = card["capabilities"]["extensions"][0]
        assert ext["params"]["guardrail_count"] == 2

    def test_no_governance_no_extension(self, tmp_path):
        ir = _make_ir()
        card = _emit_and_load(ir, tmp_path)
        caps = card["capabilities"]
        assert "extensions" not in caps or not caps.get("extensions")


# ---------------------------------------------------------------------------
# Provider and documentation URL
# ---------------------------------------------------------------------------


class TestProviderAndDocs:
    """Tests for provider and documentationUrl fields."""

    def test_author_populates_provider(self, tmp_path):
        ir = _make_ir(author="ACME Corp")
        card = _emit_and_load(ir, tmp_path)
        assert "provider" in card
        assert card["provider"]["organization"] == "ACME Corp"

    def test_homepage_populates_documentation_url(self, tmp_path):
        ir = _make_ir(homepage="https://example.com/docs")
        card = _emit_and_load(ir, tmp_path)
        assert "documentationUrl" in card
        assert card["documentationUrl"] == "https://example.com/docs"

    def test_no_author_no_provider(self, tmp_path):
        ir = _make_ir()  # no author or homepage
        card = _emit_and_load(ir, tmp_path)
        assert "provider" not in card

    def test_version_from_ir(self, tmp_path):
        ir = _make_ir(version="2.5.0")
        card = _emit_and_load(ir, tmp_path)
        assert card["version"] == "2.5.0"


# ---------------------------------------------------------------------------
# README.md generation
# ---------------------------------------------------------------------------


class TestReadmeGeneration:
    """Tests for README.md generation alongside agent-card.json."""

    def test_readme_created(self, tmp_path):
        ir = _make_ir()
        a2a_emitter.emit(ir, tmp_path)
        assert (tmp_path / "README.md").exists()

    def test_readme_contains_agent_name(self, tmp_path):
        ir = _make_ir(name="my-cool-agent")
        a2a_emitter.emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "my-cool-agent" in readme

    def test_readme_contains_a2a_reference(self, tmp_path):
        ir = _make_ir()
        a2a_emitter.emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "A2A" in readme or "agent-card" in readme.lower()


# ---------------------------------------------------------------------------
# Triggers → streaming / push notifications
# ---------------------------------------------------------------------------


class TestTriggersCapabilities:
    """Tests for how triggers influence streaming and pushNotifications."""

    def test_webhook_trigger_enables_push_notifications(self, tmp_path):
        ir = _make_ir(triggers=[Trigger(kind="webhook")])
        card = _emit_and_load(ir, tmp_path)
        assert card["capabilities"]["pushNotifications"] is True

    def test_event_trigger_enables_streaming(self, tmp_path):
        ir = _make_ir(triggers=[Trigger(kind="event")])
        card = _emit_and_load(ir, tmp_path)
        assert card["capabilities"]["streaming"] is True

    def test_cron_trigger_no_streaming(self, tmp_path):
        ir = _make_ir(triggers=[Trigger(kind="cron", cron_expr="0 * * * *")])
        card = _emit_and_load(ir, tmp_path)
        # cron alone doesn't enable streaming
        assert card["capabilities"]["streaming"] is False


# ---------------------------------------------------------------------------
# Fixture conversion: pregnancy-companion → A2A card
# ---------------------------------------------------------------------------


class TestFixtureConversion:
    """Parse a real fixture and emit an A2A card."""

    @pytest.mark.skipif(
        not PREGNANCY_COMPANION_DIR.exists(),
        reason="pregnancy-companion fixture not found",
    )
    def test_pregnancy_companion_emits_valid_card(self, tmp_path):
        ir = parse_openclaw(PREGNANCY_COMPANION_DIR)
        card = _emit_and_load(ir, tmp_path)

        for field in (
            "name",
            "description",
            "version",
            "supportedInterfaces",
            "capabilities",
            "skills",
        ):
            assert field in card, f"Required field {field!r} missing"

    @pytest.mark.skipif(
        not PREGNANCY_COMPANION_DIR.exists(),
        reason="pregnancy-companion fixture not found",
    )
    def test_pregnancy_companion_skills_populated(self, tmp_path):
        ir = parse_openclaw(PREGNANCY_COMPANION_DIR)
        card = _emit_and_load(ir, tmp_path)
        assert len(card["skills"]) >= 1

    @pytest.mark.skipif(
        not PREGNANCY_COMPANION_DIR.exists(),
        reason="pregnancy-companion fixture not found",
    )
    def test_pregnancy_companion_card_is_valid_json(self, tmp_path):
        """The emitted file must be parseable as JSON."""
        ir = parse_openclaw(PREGNANCY_COMPANION_DIR)
        a2a_emitter.emit(ir, tmp_path)
        card_text = (tmp_path / "agent-card.json").read_text(encoding="utf-8")
        # Should not raise
        json.loads(card_text)


# ---------------------------------------------------------------------------
# Output directory creation
# ---------------------------------------------------------------------------


class TestOutputDirectory:
    """emit() should create the output directory if it doesn't exist."""

    def test_creates_nested_output_dir(self, tmp_path):
        out_dir = tmp_path / "nested" / "a2a" / "output"
        ir = _make_ir()
        a2a_emitter.emit(ir, out_dir)
        assert out_dir.exists()
        assert (out_dir / "agent-card.json").exists()

    def test_agent_card_is_valid_json(self, tmp_path):
        ir = _make_ir()
        a2a_emitter.emit(ir, tmp_path)
        content = (tmp_path / "agent-card.json").read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_agent_card_ends_with_newline(self, tmp_path):
        ir = _make_ir()
        a2a_emitter.emit(ir, tmp_path)
        content = (tmp_path / "agent-card.json").read_text(encoding="utf-8")
        assert content.endswith("\n")
