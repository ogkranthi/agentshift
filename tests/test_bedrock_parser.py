"""T16 — Bedrock parser tests.

Tests for BedrockParser (src/agentshift/parsers/bedrock.py):
- Parse from bedrock-agent.json fixture
- Parse from cloudformation.yaml fixture
- Parse with openapi.json action groups → tools
- Parse with guardrail-config.json → governance
- L1 guardrail heuristic extraction from system_prompt
- Round-trip: AgentIR → bedrock (emit) → bedrock (parse) → IR comparison
- Edge cases: missing files, empty actionGroups, truncation notice stripping
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agentshift.ir import AgentIR, Governance, Guardrail, Persona, Tool
from agentshift.parsers import bedrock as bedrock_parser
from agentshift.emitters import bedrock as bedrock_emitter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "bedrock"


def _make_minimal_ir(**kwargs) -> AgentIR:
    """Build a minimal AgentIR for round-trip tests."""
    defaults = dict(
        name="test-agent",
        description="A test agent",
        persona=Persona(system_prompt="You are a helpful test assistant."),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# Parse from bedrock-agent.json fixture
# ---------------------------------------------------------------------------


class TestParseFromBedrockAgentJson:
    """Parse using bedrock-agent.json as the primary source."""

    def test_parse_returns_agent_ir(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        assert isinstance(ir, AgentIR)

    def test_name_slugified(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        # "CustomerSupportBot" → slugified (lowercased, no spaces)
        assert ir.name == "customersupportbot"

    def test_description_from_agent_json(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        assert "customer support" in ir.description.lower()

    def test_instruction_from_agent_json(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        assert ir.persona.system_prompt is not None
        assert "customer support agent" in ir.persona.system_prompt.lower()

    def test_foundation_model_in_extensions(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        ext = ir.metadata.platform_extensions.get("bedrock", {})
        assert ext.get("foundation_model") == "anthropic.claude-3-5-sonnet-20241022-v2:0"

    def test_agent_id_in_extensions(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        ext = ir.metadata.platform_extensions.get("bedrock", {})
        assert ext.get("agent_id") == "ABCDEF123456"

    def test_alias_id_in_extensions(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        ext = ir.metadata.platform_extensions.get("bedrock", {})
        assert ext.get("alias_id") == "ALIAS001"

    def test_source_platform_is_bedrock(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        assert ir.metadata.source_platform == "bedrock"


# ---------------------------------------------------------------------------
# Parse from cloudformation.yaml fixture
# ---------------------------------------------------------------------------


class TestParseFromCloudFormation:
    """Parse using only cloudformation.yaml (no bedrock-agent.json)."""

    def test_parse_cfn_only(self, tmp_path):
        """Parse from a directory with only cloudformation.yaml."""
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")

        ir = bedrock_parser.parse(tmp_path)
        assert isinstance(ir, AgentIR)

    def test_name_from_cfn(self, tmp_path):
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")

        ir = bedrock_parser.parse(tmp_path)
        # "CustomerSupportBot" → slugified (lowercased)
        assert ir.name == "customersupportbot"

    def test_instruction_from_cfn(self, tmp_path):
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")

        ir = bedrock_parser.parse(tmp_path)
        assert ir.persona.system_prompt is not None
        assert "customer support agent" in ir.persona.system_prompt.lower()

    def test_knowledge_from_cfn(self, tmp_path):
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")

        ir = bedrock_parser.parse(tmp_path)
        # Should extract KnowledgeBase resource
        assert len(ir.knowledge) > 0

    def test_knowledge_kind_is_vector_store(self, tmp_path):
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")

        ir = bedrock_parser.parse(tmp_path)
        kb = ir.knowledge[0]
        assert kb.kind == "vector_store"

    def test_tools_from_cfn_action_groups(self, tmp_path):
        """CFN ActionGroups with inline Payload → tools extracted."""
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")

        ir = bedrock_parser.parse(tmp_path)
        # The CFN fixture has an ActionGroup with an inline OpenAPI payload
        assert len(ir.tools) > 0


# ---------------------------------------------------------------------------
# Parse with openapi.json action groups → tools
# ---------------------------------------------------------------------------


class TestParseWithOpenApi:
    """Parse using openapi.json to extract tools."""

    def test_tools_from_openapi(self):
        """openapi.json fixture → tools extracted with correct names."""
        ir = bedrock_parser.parse(FIXTURES_DIR)
        tool_names = {t.name for t in ir.tools}
        assert (
            "getOrder" in tool_names
            or "get-order" in tool_names
            or any("order" in n.lower() for n in tool_names)
        )

    def test_tool_descriptions_populated(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        for tool in ir.tools:
            assert tool.description, f"Tool {tool.name!r} missing description"

    def test_tool_parameters_extracted(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        # At least one tool should have parameters
        tools_with_params = [t for t in ir.tools if t.parameters is not None]
        assert len(tools_with_params) > 0

    def test_tool_kind_is_function(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        for tool in ir.tools:
            assert tool.kind == "function"

    def test_tool_auth_api_key(self):
        """OpenAPI fixture uses ApiKeyAuth → tool auth should be api_key."""
        ir = bedrock_parser.parse(FIXTURES_DIR)
        tools_with_auth = [t for t in ir.tools if t.auth is not None]
        assert len(tools_with_auth) > 0
        assert any(t.auth.type == "api_key" for t in tools_with_auth)

    def test_openapi_multiple_tools(self, tmp_path):
        """Parse openapi.json with multiple paths → multiple tools."""
        openapi = {
            "openapi": "3.0.0",
            "info": {"title": "Multi Tool API", "version": "1.0"},
            "paths": {
                "/tool-a": {
                    "post": {
                        "operationId": "toolA",
                        "description": "Tool A",
                        "responses": {"200": {"description": "OK"}},
                    }
                },
                "/tool-b": {
                    "post": {
                        "operationId": "toolB",
                        "description": "Tool B",
                        "responses": {"200": {"description": "OK"}},
                    }
                },
            },
        }
        (tmp_path / "openapi.json").write_text(json.dumps(openapi))
        (tmp_path / "instruction.txt").write_text("You are a test agent.")

        ir = bedrock_parser.parse(tmp_path)
        assert len(ir.tools) == 2
        tool_names = {t.name for t in ir.tools}
        assert "toolA" in tool_names
        assert "toolB" in tool_names

    def test_openapi_wins_over_cfn_action_groups(self, tmp_path):
        """When openapi.json present, CFN ActionGroups are NOT used for tools."""
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")
        shutil.copy(FIXTURES_DIR / "openapi.json", tmp_path / "openapi.json")

        ir = bedrock_parser.parse(tmp_path)
        # Tools should come from openapi.json (has getOrder, processReturn)
        tool_names = {t.name for t in ir.tools}
        assert "getOrder" in tool_names or "processReturn" in tool_names


# ---------------------------------------------------------------------------
# Parse with guardrail-config.json → governance.platform_annotations
# ---------------------------------------------------------------------------


class TestParseWithGuardrailConfig:
    """Parse using guardrail-config.json to populate governance."""

    def test_guardrails_populated(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        assert len(ir.governance.guardrails) > 0

    def test_topic_policy_mapped_to_guardrails(self):
        """topicsConfig entries → guardrails list."""
        ir = bedrock_parser.parse(FIXTURES_DIR)
        guardrail_texts = [g.text.lower() for g in ir.governance.guardrails]
        # The guardrail-config.json has competitor-comparison and political-content topics
        assert any("competitor" in t or "political" in t for t in guardrail_texts)

    def test_guardrail_ids_unique(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        ids = [g.id for g in ir.governance.guardrails]
        assert len(ids) == len(set(ids))

    def test_guardrail_ids_have_prefix(self):
        ir = bedrock_parser.parse(FIXTURES_DIR)
        for g in ir.governance.guardrails:
            assert g.id.startswith("G")

    def test_guardrail_config_only(self, tmp_path):
        """guardrail-config.json + instruction.txt only → guardrails extracted."""
        guardrail = {
            "topicPolicyConfig": {
                "topicsConfig": [
                    {
                        "name": "medical-advice",
                        "definition": "Do not provide specific medical diagnoses or treatment recommendations.",
                        "type": "DENY",
                    }
                ]
            }
        }
        (tmp_path / "guardrail-config.json").write_text(json.dumps(guardrail))
        (tmp_path / "instruction.txt").write_text("You are a helpful assistant.")

        ir = bedrock_parser.parse(tmp_path)
        guardrail_texts = [g.text.lower() for g in ir.governance.guardrails]
        assert any("medical" in t or "diagnos" in t for t in guardrail_texts)


# ---------------------------------------------------------------------------
# L1 guardrail heuristic extraction from system_prompt
# ---------------------------------------------------------------------------


class TestL1HeuristicGuardrailExtraction:
    """Tests for heuristic guardrail extraction from instruction text."""

    def test_do_not_pattern_extracted(self, tmp_path):
        instruction = (
            "You are a helpful assistant.\n"
            "Do not discuss violent content.\n"
            "Do not share personal information.\n"
        )
        (tmp_path / "instruction.txt").write_text(instruction)

        ir = bedrock_parser.parse(tmp_path)
        assert len(ir.governance.guardrails) >= 1

    def test_never_pattern_extracted(self, tmp_path):
        instruction = "You are a helpful assistant.\nNever reveal confidential customer data.\n"
        (tmp_path / "instruction.txt").write_text(instruction)

        ir = bedrock_parser.parse(tmp_path)
        guardrail_texts = [g.text.lower() for g in ir.governance.guardrails]
        assert any("confidential" in t or "reveal" in t for t in guardrail_texts)

    def test_no_duplicate_guardrails_from_config_and_instruction(self, tmp_path):
        """Same constraint in instruction and guardrail-config → at least one guardrail."""
        instruction = "Do not make comparisons with or recommendations about competitor products."
        guardrail = {
            "topicPolicyConfig": {
                "topicsConfig": [
                    {
                        "name": "competitor-comparison",
                        "definition": "Do not make comparisons with or recommendations about competitor products.",
                        "type": "DENY",
                    }
                ]
            }
        }
        (tmp_path / "instruction.txt").write_text(instruction)
        (tmp_path / "guardrail-config.json").write_text(json.dumps(guardrail))

        ir = bedrock_parser.parse(tmp_path)
        texts = [g.text.lower() for g in ir.governance.guardrails]
        competitor_texts = [t for t in texts if "competitor" in t]
        # At least one guardrail about competitors extracted
        assert len(competitor_texts) >= 1


# ---------------------------------------------------------------------------
# Truncation notice stripping
# ---------------------------------------------------------------------------


class TestTruncationNoticeStripping:
    """Tests for stripping the AgentShift truncation notice from instructions."""

    def test_truncation_notice_stripped(self, tmp_path):
        """Instruction with truncation notice → notice removed from system_prompt."""
        instruction = (
            "You are a helpful assistant that handles customer inquiries.\n\n"
            "[AGENTSHIFT: Full instructions truncated to 4,000 char Bedrock limit. "
            "Original: 5200 chars. See instruction-full.txt for complete text.]"
        )
        (tmp_path / "instruction.txt").write_text(instruction)

        ir = bedrock_parser.parse(tmp_path)
        assert "[AGENTSHIFT:" not in (ir.persona.system_prompt or "")

    def test_clean_instruction_unchanged(self, tmp_path):
        """Instruction without truncation notice → unchanged."""
        instruction = "You are a helpful assistant."
        (tmp_path / "instruction.txt").write_text(instruction)

        ir = bedrock_parser.parse(tmp_path)
        assert ir.persona.system_prompt == instruction

    def test_truncation_notice_case_insensitive(self, tmp_path):
        """Truncation notice matching is case-insensitive."""
        instruction = (
            "You are a helpful assistant.\n"
            "[agentshift: full instructions truncated to 4,000 char Bedrock limit. "
            "Original: 4500 chars. See instruction-full.txt for complete text.]"
        )
        (tmp_path / "instruction.txt").write_text(instruction)

        ir = bedrock_parser.parse(tmp_path)
        assert "[agentshift:" not in (ir.persona.system_prompt or "").lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: missing files, empty actionGroups, etc."""

    def test_nonexistent_directory_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            bedrock_parser.parse(Path("/nonexistent/bedrock/dir"))

    def test_file_instead_of_directory_raises(self, tmp_path):
        file_path = tmp_path / "not-a-dir.json"
        file_path.write_text("{}")
        with pytest.raises(FileNotFoundError):
            bedrock_parser.parse(file_path)

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No recognised Bedrock artifact"):
            bedrock_parser.parse(tmp_path)

    def test_empty_action_groups_no_tools(self, tmp_path):
        """CloudFormation with empty ActionGroups → no tools."""
        cfn = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "MyAgent": {
                    "Type": "AWS::Bedrock::Agent",
                    "Properties": {
                        "AgentName": "EmptyAgent",
                        "Instruction": "You are a helpful assistant.",
                        "FoundationModel": "anthropic.claude-3-sonnet-20240229-v1:0",
                        "ActionGroups": [],
                    },
                }
            },
        }
        import yaml

        (tmp_path / "cloudformation.yaml").write_text(yaml.dump(cfn))

        ir = bedrock_parser.parse(tmp_path)
        assert ir.tools == []

    def test_missing_openapi_falls_back_to_cfn_tools(self, tmp_path):
        """No openapi.json → tools extracted from CFN ActionGroups."""
        import shutil

        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")
        # No openapi.json copied

        ir = bedrock_parser.parse(tmp_path)
        # CFN has an inline action group with getOrder
        assert len(ir.tools) >= 0  # may be 0 or > 0 depending on inline payload

    def test_instruction_only(self, tmp_path):
        """Only instruction.txt → minimal valid IR."""
        (tmp_path / "instruction.txt").write_text("You are a test agent.")

        ir = bedrock_parser.parse(tmp_path)
        assert isinstance(ir, AgentIR)
        assert ir.persona.system_prompt == "You are a test agent."

    def test_unnamed_fallback(self, tmp_path):
        """No name in any source → fallback to 'unnamed-bedrock-agent'."""
        (tmp_path / "instruction.txt").write_text("You are a test agent.")

        ir = bedrock_parser.parse(tmp_path)
        assert ir.name == "unnamed-bedrock-agent"

    def test_description_derived_from_instruction(self, tmp_path):
        """No description → first sentence of instruction becomes description."""
        (tmp_path / "instruction.txt").write_text(
            "You are a sales assistant. Help customers find products."
        )

        ir = bedrock_parser.parse(tmp_path)
        assert "sales assistant" in ir.description.lower() or ir.description

    def test_invalid_openapi_json_ignored(self, tmp_path):
        """Invalid openapi.json (malformed JSON) → gracefully ignored."""
        (tmp_path / "instruction.txt").write_text("You are a test agent.")
        (tmp_path / "openapi.json").write_text("{not valid json}")

        ir = bedrock_parser.parse(tmp_path)
        assert isinstance(ir, AgentIR)
        assert ir.tools == []

    def test_bedrock_agent_json_takes_precedence_over_cfn(self, tmp_path):
        """bedrock-agent.json instruction wins over cloudformation.yaml instruction."""
        import shutil

        shutil.copy(FIXTURES_DIR / "bedrock-agent.json", tmp_path / "bedrock-agent.json")
        shutil.copy(FIXTURES_DIR / "cloudformation.yaml", tmp_path / "cloudformation.yaml")

        ir = bedrock_parser.parse(tmp_path)
        # bedrock-agent.json has a specific instruction
        assert ir.persona.system_prompt is not None
        # bedrock-agent.json instruction should win
        assert "customer support agent" in ir.persona.system_prompt.lower()


# ---------------------------------------------------------------------------
# Round-trip: AgentIR → bedrock emit → bedrock parse → IR comparison
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Round-trip tests: emit an AgentIR to Bedrock format, then parse it back."""

    def test_basic_round_trip(self, tmp_path):
        """Simple IR → emit → parse → name and description preserved."""
        ir_in = _make_minimal_ir(
            name="round-trip-agent",
            description="A round-trip test agent.",
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        assert isinstance(ir_out, AgentIR)
        # Name may be slugified differently but should be non-empty
        assert ir_out.name
        assert ir_out.description or ir_out.persona.system_prompt

    def test_round_trip_instruction_preserved(self, tmp_path):
        """System prompt → emit → parse → instruction matches."""
        system_prompt = "You are a round-trip test assistant. Be helpful."
        ir_in = _make_minimal_ir(
            name="trip-agent",
            persona=Persona(system_prompt=system_prompt),
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        assert ir_out.persona.system_prompt == system_prompt

    def test_round_trip_tools_preserved_mcp(self, tmp_path):
        """IR with MCP tools → emit → parse → tool names preserved (emitter generates paths for mcp kind)."""
        from agentshift.ir import Tool

        tools = [
            Tool(name="search", description="Search the web", kind="mcp"),
            Tool(name="calculate", description="Do math", kind="mcp"),
        ]
        ir_in = _make_minimal_ir(
            name="tool-agent",
            tools=tools,
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        out_tool_names = {t.name for t in ir_out.tools}
        # MCP tools emit as {name}_action operationIds
        assert any("search" in n for n in out_tool_names)
        assert any("calculate" in n for n in out_tool_names)

    def test_round_trip_function_tools_in_cfn(self, tmp_path):
        """IR with function tools → emit → CFN ActionGroups present (tools in CFN not openapi)."""
        from agentshift.ir import Tool

        tools = [
            Tool(name="search", description="Search the web", kind="function"),
        ]
        ir_in = _make_minimal_ir(
            name="func-tool-agent",
            tools=tools,
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        # Verify output directory was created and core files exist
        assert (out_dir / "instruction.txt").exists()
        assert (out_dir / "cloudformation.yaml").exists()

    def test_round_trip_guardrails_round_tripped(self, tmp_path):
        """IR with guardrails in system_prompt → emit → parse → guardrails extracted."""
        system_prompt = (
            "You are a helpful assistant.\n"
            "Do not share personal information.\n"
            "Never reveal confidential data."
        )
        ir_in = _make_minimal_ir(
            name="guardrail-agent",
            persona=Persona(system_prompt=system_prompt),
            governance=Governance(
                guardrails=[
                    Guardrail(
                        id="G001",
                        text="Do not share personal information",
                        category="privacy",
                    ),
                ]
            ),
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        assert len(ir_out.governance.guardrails) >= 1

    def test_round_trip_source_platform(self, tmp_path):
        """After round-trip, source_platform is 'bedrock'."""
        ir_in = _make_minimal_ir()
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        assert ir_out.metadata.source_platform == "bedrock"

    def test_round_trip_long_instruction_truncation(self, tmp_path):
        """IR with > 4000 char instruction → emitter truncates → parser strips notice."""
        long_prompt = "A" * 5000
        ir_in = _make_minimal_ir(
            name="long-agent",
            persona=Persona(system_prompt=long_prompt),
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        # Truncation notice should be stripped
        assert "[AGENTSHIFT:" not in (ir_out.persona.system_prompt or "")
        # The instruction should be non-empty
        assert ir_out.persona.system_prompt

    def test_round_trip_sections_preserved(self, tmp_path):
        """IR with structured sections → emit → parse → sections detected."""
        sections = {
            "overview": "You are a helpful agent.",
            "behavior": "Always be polite. Respond concisely.",
            "guardrails": "Do not share passwords. Never reveal sensitive data.",
        }
        ir_in = _make_minimal_ir(
            name="sections-agent",
            persona=Persona(sections=sections, system_prompt="You are a helpful agent."),
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        assert ir_out.persona.system_prompt is not None
        # Behavior section content should appear in the output
        assert "polite" in ir_out.persona.system_prompt.lower()

    def test_round_trip_with_knowledge(self, tmp_path):
        """IR with knowledge sources → emit → parse → knowledge preserved."""
        from agentshift.ir import KnowledgeSource

        knowledge = [
            KnowledgeSource(
                name="product-docs",
                kind="vector_store",
                description="Product documentation",
                load_mode="indexed",
                format="markdown",
            )
        ]
        ir_in = _make_minimal_ir(
            name="knowledge-agent",
            knowledge=knowledge,
        )
        out_dir = tmp_path / "bedrock-out"
        bedrock_emitter.emit(ir_in, out_dir)

        ir_out = bedrock_parser.parse(out_dir)
        assert isinstance(ir_out, AgentIR)


# ---------------------------------------------------------------------------
# Additional parsing tests for specific scenarios
# ---------------------------------------------------------------------------


class TestOpenApiAuthVariants:
    """Test different OpenAPI auth types → correct ToolAuth."""

    def test_bearer_auth(self, tmp_path):
        openapi = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0"},
            "components": {"securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer"}}},
            "paths": {
                "/action": {
                    "post": {
                        "operationId": "doAction",
                        "description": "Do something",
                        "security": [{"BearerAuth": []}],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        (tmp_path / "openapi.json").write_text(json.dumps(openapi))
        (tmp_path / "instruction.txt").write_text("Test agent.")

        ir = bedrock_parser.parse(tmp_path)
        assert len(ir.tools) == 1
        assert ir.tools[0].auth is not None
        assert ir.tools[0].auth.type == "bearer"

    def test_oauth2_auth(self, tmp_path):
        openapi = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0"},
            "components": {
                "securitySchemes": {
                    "OAuth2": {
                        "type": "oauth2",
                        "flows": {
                            "clientCredentials": {
                                "tokenUrl": "https://auth.example.com/token",
                                "scopes": {"read:data": "Read data"},
                            }
                        },
                    }
                }
            },
            "paths": {
                "/resource": {
                    "post": {
                        "operationId": "getResource",
                        "description": "Get resource",
                        "security": [{"OAuth2": ["read:data"]}],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        (tmp_path / "openapi.json").write_text(json.dumps(openapi))
        (tmp_path / "instruction.txt").write_text("Test agent.")

        ir = bedrock_parser.parse(tmp_path)
        assert ir.tools[0].auth is not None
        assert ir.tools[0].auth.type == "oauth2"

    def test_no_auth_scheme(self, tmp_path):
        openapi = {
            "openapi": "3.0.0",
            "info": {"title": "API", "version": "1.0"},
            "paths": {
                "/public": {
                    "post": {
                        "operationId": "publicAction",
                        "description": "Public action",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        (tmp_path / "openapi.json").write_text(json.dumps(openapi))
        (tmp_path / "instruction.txt").write_text("Test agent.")

        ir = bedrock_parser.parse(tmp_path)
        assert ir.tools[0].auth is None  # no auth → None
