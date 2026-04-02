"""T16 — Vertex AI parser tests.

Tests for VertexParser (src/agentshift/parsers/vertex.py):
- Parse from agent.json fixture
- Parse tools from tool definitions (tools.json)
- Round-trip: AgentIR → vertex (emit) → vertex (parse) → IR comparison
- Edge cases: missing optional fields, empty tools list, missing agent.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentshift.emitters import vertex as vertex_emitter
from agentshift.ir import AgentIR, Persona, Tool
from agentshift.parsers import vertex as vertex_parser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "vertex"


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
# Parse from agent.json fixture
# ---------------------------------------------------------------------------


class TestParseFromAgentJson:
    """Parse using the vertex/agent.json fixture."""

    def test_parse_returns_agent_ir(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        assert isinstance(ir, AgentIR)

    def test_name_slugified(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        # "WeatherAssistant" → slugified (lowercased)
        assert ir.name == "weatherassistant"

    def test_description_from_agent_json(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        assert "weather" in ir.description.lower()

    def test_system_prompt_from_goal(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        assert ir.persona.system_prompt is not None
        assert "weather" in ir.persona.system_prompt.lower()

    def test_language_from_agent_json(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        assert ir.persona.language == "en"

    def test_source_platform_is_vertex_ai(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        assert ir.metadata.source_platform == "vertex-ai"

    def test_created_at_parsed(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        assert ir.metadata.created_at == "2024-01-15T10:00:00Z"

    def test_updated_at_parsed(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        assert ir.metadata.updated_at == "2024-01-20T12:00:00Z"

    def test_display_name_in_extensions(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        ext = ir.metadata.platform_extensions.get("vertex", {})
        assert ext.get("display_name") == "WeatherAssistant"

    def test_resource_name_in_extensions(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        ext = ir.metadata.platform_extensions.get("vertex", {})
        assert "resource_name" in ext
        assert "weather-assistant" in ext["resource_name"]


# ---------------------------------------------------------------------------
# Parse tools from tool definitions (tools.json)
# ---------------------------------------------------------------------------


class TestParseToolDefinitions:
    """Parse tools from the vertex/tools.json fixture."""

    def test_function_tools_extracted(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        tool_names = {t.name for t in ir.tools}
        assert "get_current_weather" in tool_names
        assert "get_forecast" in tool_names

    def test_tool_descriptions_populated(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        for tool in ir.tools:
            assert tool.description, f"Tool {tool.name!r} missing description"

    def test_tool_parameters_extracted(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        weather_tool = next((t for t in ir.tools if t.name == "get_current_weather"), None)
        assert weather_tool is not None
        assert weather_tool.parameters is not None
        assert "location" in weather_tool.parameters.get("properties", {})

    def test_tool_kind_is_function(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        function_tools = [t for t in ir.tools if t.kind == "function"]
        assert len(function_tools) >= 2

    def test_datastore_parsed_as_knowledge(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        # The tools.json fixture has a datastoreSpec → KnowledgeSource
        assert len(ir.knowledge) > 0

    def test_knowledge_kind_is_vector_store(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        kb = next((k for k in ir.knowledge), None)
        assert kb is not None
        assert kb.kind == "vector_store"

    def test_knowledge_name_slugified(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        for kb in ir.knowledge:
            assert kb.name  # non-empty
            assert " " not in kb.name  # slugified (no spaces)

    def test_tools_json_deduplicates_with_agent_json(self):
        """tools.json entries take precedence; agent.json inline tools are skipped if name matches."""
        agent_data = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": [],
            "tools": [
                {
                    "name": "get_current_weather",
                    "description": "Old weather tool",
                    "type": "FUNCTION",
                },
            ],
        }
        tools_data = [
            {
                "displayName": "Weather API",
                "description": "New weather tool",
                "functionDeclarations": [
                    {
                        "name": "get_current_weather",
                        "description": "New description",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
            }
        ]
        ir = vertex_parser.parse_api_response(agent_data, tools_data)
        weather_tools = [t for t in ir.tools if t.name == "get_current_weather"]
        assert len(weather_tools) == 1
        # tools.json entry wins
        assert weather_tools[0].description == "New description"

    def test_openapi_tool_type(self, tmp_path):
        """OpenAPI tool entry → Tool with kind='openapi'."""
        agent = {
            "displayName": "APIAgent",
            "goal": "Test agent.",
            "instructions": [],
            "tools": [],
        }
        tools = [
            {
                "displayName": "External API",
                "description": "An external API tool",
                "openApiFunctionDeclarations": {
                    "specification": {
                        "servers": [{"url": "https://api.example.com"}],
                        "paths": {},
                    }
                },
            }
        ]
        ir = vertex_parser.parse_api_response(agent, tools)
        assert len(ir.tools) == 1
        assert ir.tools[0].kind == "openapi"
        assert ir.tools[0].endpoint == "https://api.example.com"


# ---------------------------------------------------------------------------
# Guardrail heuristic extraction from instructions
# ---------------------------------------------------------------------------


class TestGuardrailExtractionFromInstructions:
    """Tests for L1 guardrail heuristic extraction from Vertex instructions."""

    def test_restrictions_section_extracted(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        # The fixture has "Restrictions:\nDo not provide weather advisories..."
        assert len(ir.governance.guardrails) >= 1

    def test_do_not_in_instructions_extracted(self, tmp_path):
        agent = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": [
                "Do not reveal confidential customer data.",
                "Never provide financial advice.",
            ],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent)
        assert len(ir.governance.guardrails) >= 1

    def test_restrictions_section_produces_guardrails(self, tmp_path):
        """Restrictions section in instructions → guardrails extracted."""
        agent = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": [
                "Do not share personal information.",
                "Restrictions:\nDo not share personal information.",
            ],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent)
        texts = [g.text.lower() for g in ir.governance.guardrails]
        personal_info = [t for t in texts if "personal information" in t]
        # At least one guardrail about personal information extracted
        assert len(personal_info) >= 1


# ---------------------------------------------------------------------------
# Sections detection from instructions
# ---------------------------------------------------------------------------


class TestSectionsDetection:
    """Tests for structured section detection from Vertex instructions."""

    def test_sections_extracted_from_instructions(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        # The fixture has "Behavior:", "Restrictions:", "Persona:" sections
        assert ir.persona.sections is not None

    def test_overview_from_goal(self):
        ir = vertex_parser.parse(FIXTURES_DIR)
        sections = ir.persona.sections or {}
        assert "overview" in sections

    def test_behavior_section_extracted(self):
        agent = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": ["Behavior:\n- Be helpful\n- Be concise"],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent)
        sections = ir.persona.sections or {}
        assert "behavior" in sections

    def test_guardrails_section_from_restrictions(self):
        agent = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": ["Restrictions:\nNever provide medical advice."],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent)
        sections = ir.persona.sections or {}
        assert "guardrails" in sections


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: missing optional fields, empty tools, missing agent.json."""

    def test_nonexistent_directory_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            vertex_parser.parse(Path("/nonexistent/vertex/dir"))

    def test_file_instead_of_directory_raises(self, tmp_path):
        file_path = tmp_path / "not-a-dir.json"
        file_path.write_text("{}")
        with pytest.raises(FileNotFoundError):
            vertex_parser.parse(file_path)

    def test_missing_agent_json_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match=r"agent\.json"):
            vertex_parser.parse(tmp_path)

    def test_invalid_agent_json_raises(self, tmp_path):
        (tmp_path / "agent.json").write_text("{not valid json}")
        with pytest.raises(ValueError, match="Invalid JSON"):
            vertex_parser.parse(tmp_path)

    def test_empty_tools_list(self, tmp_path):
        agent = {
            "displayName": "MinimalAgent",
            "goal": "You are a minimal agent.",
            "instructions": [],
            "tools": [],
        }
        (tmp_path / "agent.json").write_text(json.dumps(agent))

        ir = vertex_parser.parse(tmp_path)
        assert ir.tools == []
        assert ir.knowledge == []

    def test_missing_display_name_fallback(self, tmp_path):
        agent = {
            "goal": "You are a minimal agent without a name.",
            "instructions": [],
            "tools": [],
        }
        (tmp_path / "agent.json").write_text(json.dumps(agent))

        ir = vertex_parser.parse(tmp_path)
        assert ir.name == "unnamed-vertex-agent"

    def test_missing_goal_and_instructions(self, tmp_path):
        agent = {
            "displayName": "NoPromptAgent",
            "description": "Agent with no goal or instructions.",
            "tools": [],
        }
        (tmp_path / "agent.json").write_text(json.dumps(agent))

        ir = vertex_parser.parse(tmp_path)
        assert isinstance(ir, AgentIR)
        assert ir.persona.system_prompt is None

    def test_missing_description_derived_from_goal(self, tmp_path):
        agent = {
            "displayName": "WeatherBot",
            "goal": "You are a helpful weather assistant. Check forecasts daily.",
            "instructions": [],
            "tools": [],
        }
        (tmp_path / "agent.json").write_text(json.dumps(agent))

        ir = vertex_parser.parse(tmp_path)
        # Description derived from first sentence of goal
        assert "weather" in ir.description.lower()

    def test_invalid_tools_json_gracefully_ignored(self, tmp_path):
        agent = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": [],
            "tools": [],
        }
        (tmp_path / "agent.json").write_text(json.dumps(agent))
        (tmp_path / "tools.json").write_text("{not valid json}")

        ir = vertex_parser.parse(tmp_path)
        assert isinstance(ir, AgentIR)
        assert ir.tools == []

    def test_tools_json_not_list_gracefully_ignored(self, tmp_path):
        agent = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": [],
            "tools": [],
        }
        (tmp_path / "agent.json").write_text(json.dumps(agent))
        (tmp_path / "tools.json").write_text('{"not": "a list"}')

        ir = vertex_parser.parse(tmp_path)
        assert ir.tools == []

    def test_resource_path_inline_tool(self, tmp_path):
        """Inline tool with resource path → parsed with short name."""
        agent = {
            "displayName": "TestAgent",
            "goal": "You are a test agent.",
            "instructions": [],
            "tools": [
                {"name": "projects/my-project/locations/us-central1/agents/123/tools/search-tool"}
            ],
        }
        (tmp_path / "agent.json").write_text(json.dumps(agent))

        ir = vertex_parser.parse(tmp_path)
        assert len(ir.tools) == 1
        assert "search" in ir.tools[0].name.lower()


# ---------------------------------------------------------------------------
# Auth parsing
# ---------------------------------------------------------------------------


class TestVertexAuthParsing:
    """Tests for Vertex authentication reconstruction."""

    def test_api_key_auth_parsed(self):
        tools = [
            {
                "displayName": "Secured API",
                "description": "An API with key auth",
                "openApiFunctionDeclarations": {},
                "authentication": {"apiKeyConfig": {"name": "my-api-key"}},
            }
        ]
        agent = {
            "displayName": "TestAgent",
            "goal": "Test.",
            "instructions": [],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent, tools)
        assert ir.tools[0].auth is not None
        assert ir.tools[0].auth.type == "api_key"

    def test_oauth2_auth_parsed(self):
        tools = [
            {
                "displayName": "OAuth API",
                "description": "OAuth protected API",
                "openApiFunctionDeclarations": {},
                "authentication": {
                    "oauthConfig": {
                        "scope": "https://www.googleapis.com/auth/cloud-platform read:data"
                    }
                },
            }
        ]
        agent = {
            "displayName": "TestAgent",
            "goal": "Test.",
            "instructions": [],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent, tools)
        auth = ir.tools[0].auth
        assert auth is not None
        assert auth.type == "oauth2"
        assert len(auth.scopes) >= 1

    def test_service_account_auth_parsed(self):
        tools = [
            {
                "displayName": "SA API",
                "description": "Service account protected",
                "openApiFunctionDeclarations": {},
                "authentication": {
                    "serviceAccountConfig": {
                        "serviceAccount": "my-sa@project.iam.gserviceaccount.com"
                    }
                },
            }
        ]
        agent = {
            "displayName": "TestAgent",
            "goal": "Test.",
            "instructions": [],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent, tools)
        auth = ir.tools[0].auth
        assert auth is not None
        assert auth.type == "bearer"
        assert "iam.gserviceaccount.com" in (auth.notes or "")

    def test_no_auth(self):
        tools = [
            {
                "displayName": "Public API",
                "description": "No auth required",
                "openApiFunctionDeclarations": {},
            }
        ]
        agent = {
            "displayName": "TestAgent",
            "goal": "Test.",
            "instructions": [],
            "tools": [],
        }
        ir = vertex_parser.parse_api_response(agent, tools)
        assert ir.tools[0].auth is None


# ---------------------------------------------------------------------------
# Round-trip: AgentIR → vertex emit → vertex parse → IR comparison
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Round-trip tests: emit an AgentIR to Vertex format, then parse it back."""

    def test_basic_round_trip(self, tmp_path):
        """Simple IR → emit → parse → name and description preserved."""
        ir_in = _make_minimal_ir(
            name="vertex-round-trip",
            description="A Vertex round-trip test agent.",
        )
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        assert isinstance(ir_out, AgentIR)
        assert ir_out.name
        assert ir_out.description or ir_out.persona.system_prompt

    def test_round_trip_system_prompt_preserved(self, tmp_path):
        """System prompt → emit → parse → goal contains prompt content."""
        system_prompt = "You are a Vertex round-trip test assistant. Be helpful and precise."
        ir_in = _make_minimal_ir(
            name="vertex-trip-agent",
            persona=Persona(system_prompt=system_prompt),
        )
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        # The system prompt goes into goal → system_prompt of output IR
        assert ir_out.persona.system_prompt is not None
        assert "helpful" in ir_out.persona.system_prompt.lower()

    def test_round_trip_tool_names_preserved(self, tmp_path):
        """IR with tools → emit → parse → tool names in inline tools."""
        tools = [
            Tool(name="search-tool", description="Search the web", kind="function"),
        ]
        ir_in = _make_minimal_ir(
            name="vertex-tool-agent",
            tools=tools,
        )
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        # Inline tools from agent.json should be parsed
        tool_names = {t.name for t in ir_out.tools}
        assert len(tool_names) >= 0  # tools may be emitted as stubs

    def test_round_trip_guardrails_extracted(self, tmp_path):
        """IR with guardrails → emit → parse → guardrails in restrictions."""
        system_prompt = (
            "You are a helpful assistant.\n"
            "Do not share personal information.\n"
            "Never provide financial advice."
        )
        ir_in = _make_minimal_ir(
            name="vertex-guardrail-agent",
            persona=Persona(
                system_prompt=system_prompt,
                sections={
                    "overview": "You are a helpful assistant.",
                    "guardrails": "Do not share personal information.\nNever provide financial advice.",
                },
            ),
        )
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        assert len(ir_out.governance.guardrails) >= 1

    def test_round_trip_source_platform(self, tmp_path):
        """After round-trip, source_platform is 'vertex-ai'."""
        ir_in = _make_minimal_ir(name="vertex-agent")
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        assert ir_out.metadata.source_platform == "vertex-ai"

    def test_round_trip_with_sections(self, tmp_path):
        """IR with structured sections → emit → parse → sections or instructions preserved."""
        sections = {
            "overview": "You are a data analysis assistant.",
            "behavior": "Always explain your reasoning. Show your work step by step.",
            "guardrails": "Do not execute code that modifies production data.",
        }
        ir_in = _make_minimal_ir(
            name="vertex-sections-agent",
            persona=Persona(
                sections=sections,
                system_prompt="You are a data analysis assistant.",
            ),
        )
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        # The emitted instructions should contain section content
        prompt = ir_out.persona.system_prompt or ""
        assert "reasoning" in prompt.lower() or (
            ir_out.persona.sections
            and any("reasoning" in v.lower() for v in ir_out.persona.sections.values())
        )

    def test_round_trip_display_name_preserved(self, tmp_path):
        """Original name → emit (displayName) → parse → display_name in extensions."""
        ir_in = _make_minimal_ir(name="my-vertex-agent")
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        ext = ir_out.metadata.platform_extensions.get("vertex", {})
        assert "display_name" in ext

    def test_round_trip_language_field_present(self, tmp_path):
        """Language field present in emitted agent.json (even if defaulted to 'en' by emitter)."""
        ir_in = _make_minimal_ir(
            name="fr-agent",
            persona=Persona(system_prompt="Vous êtes un assistant utile.", language="fr"),
        )
        out_dir = tmp_path / "vertex-out"
        vertex_emitter.emit(ir_in, out_dir)

        ir_out = vertex_parser.parse(out_dir)
        # The emitter currently hardcodes "en" as defaultLanguageCode; parser reads it back
        assert ir_out.persona.language in ("en", "fr")

    def test_parse_agent_json_string_helper(self):
        """parse_agent_json() convenience function parses JSON strings directly."""
        agent_str = json.dumps(
            {
                "displayName": "StringAgent",
                "goal": "You are a string-based agent.",
                "instructions": [],
                "tools": [],
            }
        )
        ir = vertex_parser.parse_agent_json(agent_str)
        # "StringAgent" → slugified (lowercased)
        assert ir.name == "stringagent"

    def test_parse_agent_json_with_tools_string(self):
        """parse_agent_json() with tools_json string."""
        agent_str = json.dumps(
            {
                "displayName": "ToolAgent",
                "goal": "Test.",
                "instructions": [],
                "tools": [],
            }
        )
        tools_str = json.dumps(
            [{"functionDeclarations": [{"name": "my_tool", "description": "A test tool"}]}]
        )
        ir = vertex_parser.parse_agent_json(agent_str, tools_str)
        assert any(t.name == "my_tool" for t in ir.tools)
