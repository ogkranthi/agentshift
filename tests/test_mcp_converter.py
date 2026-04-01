"""Tests for the MCP-to-OpenAPI converter (src/agentshift/mcp_converter.py)."""

from __future__ import annotations

import json
from pathlib import Path

from agentshift.ir import Tool
from agentshift.mcp_converter import (
    _build_summary,
    _normalize_null_types,
    ir_tool_to_openapi_path,
    mcp_to_openapi,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture_tools() -> list[dict]:
    return json.loads((FIXTURES / "mcp_tools.json").read_text())


# ---------------------------------------------------------------------------
# mcp_to_openapi — basic structure
# ---------------------------------------------------------------------------


class TestMcpToOpenapi:
    def test_empty_tools_returns_valid_schema(self):
        schema = mcp_to_openapi([])
        assert schema["openapi"] == "3.0.0"
        assert "info" in schema
        assert schema["paths"] == {}

    def test_single_tool_creates_path(self):
        tools = [
            {
                "name": "search",
                "description": "Search files",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        schema = mcp_to_openapi(tools)
        assert "/search" in schema["paths"]

    def test_path_has_post_operation(self):
        tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        schema = mcp_to_openapi(tools)
        assert "post" in schema["paths"]["/read_file"]

    def test_operation_id_matches_tool_name(self):
        tools = [
            {
                "name": "my_tool",
                "description": "My tool",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/my_tool"]["post"]
        assert op["operationId"] == "my_tool"

    def test_description_in_operation(self):
        tools = [
            {
                "name": "tool",
                "description": "Does something useful.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/tool"]["post"]
        assert "Does something useful" in op["description"]

    def test_request_body_present(self):
        tools = [
            {
                "name": "tool",
                "description": "Tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                },
            }
        ]
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/tool"]["post"]
        assert "requestBody" in op
        assert op["requestBody"]["required"] is True

    def test_responses_200_present(self):
        tools = [
            {
                "name": "tool",
                "description": "Tool",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/tool"]["post"]
        assert "200" in op["responses"]

    def test_responses_400_and_500_present(self):
        tools = [
            {
                "name": "tool",
                "description": "Tool",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/tool"]["post"]
        assert "400" in op["responses"]
        assert "500" in op["responses"]

    def test_components_tool_result_schema_present(self):
        schema = mcp_to_openapi([])
        assert "components" in schema
        assert "ToolResult" in schema["components"]["schemas"]

    def test_tool_result_ref_in_200_response(self):
        tools = [
            {
                "name": "tool",
                "description": "Tool",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        schema = mcp_to_openapi(tools)
        resp_schema = schema["paths"]["/tool"]["post"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert resp_schema == {"$ref": "#/components/schemas/ToolResult"}

    def test_server_name_in_info(self):
        schema = mcp_to_openapi([], server_name="my-server")
        assert schema["info"]["x-mcp-server"] == "my-server"

    def test_title_override(self):
        schema = mcp_to_openapi([], title="Custom Title")
        assert schema["info"]["title"] == "Custom Title"

    def test_default_title_includes_server_name(self):
        schema = mcp_to_openapi([], server_name="github")
        assert "github" in schema["info"]["title"]

    def test_description_override(self):
        schema = mcp_to_openapi([], description="Custom description")
        assert schema["info"]["description"] == "Custom description"

    def test_servers_field_present(self):
        schema = mcp_to_openapi([])
        assert "servers" in schema
        assert len(schema["servers"]) >= 1


# ---------------------------------------------------------------------------
# mcp_to_openapi — from fixture
# ---------------------------------------------------------------------------


class TestMcpToOpenapiFixture:
    def test_fixture_tools_load(self):
        tools = _load_fixture_tools()
        assert len(tools) == 3
        assert tools[0]["name"] == "search_files"

    def test_fixture_all_tools_have_paths(self):
        tools = _load_fixture_tools()
        schema = mcp_to_openapi(tools)
        for tool in tools:
            assert f"/{tool['name']}" in schema["paths"]

    def test_search_files_has_required_pattern(self):
        tools = _load_fixture_tools()
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/search_files"]["post"]
        body_schema = op["requestBody"]["content"]["application/json"]["schema"]
        assert "pattern" in body_schema.get("properties", {})

    def test_null_type_normalized_in_base_dir(self):
        tools = _load_fixture_tools()
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/search_files"]["post"]
        body_schema = op["requestBody"]["content"]["application/json"]["schema"]
        base_dir = body_schema["properties"]["base_dir"]
        # ["string", "null"] should become "string" + nullable: true
        assert base_dir.get("nullable") is True
        assert base_dir["type"] == "string"

    def test_write_file_required_fields(self):
        tools = _load_fixture_tools()
        schema = mcp_to_openapi(tools)
        op = schema["paths"]["/write_file"]["post"]
        body_schema = op["requestBody"]["content"]["application/json"]["schema"]
        required = body_schema.get("required", [])
        assert "path" in required
        assert "content" in required

    def test_schema_is_valid_json_round_trip(self):
        tools = _load_fixture_tools()
        schema = mcp_to_openapi(tools)
        serialized = json.dumps(schema)
        parsed = json.loads(serialized)
        assert parsed["openapi"] == "3.0.0"


# ---------------------------------------------------------------------------
# _normalize_null_types
# ---------------------------------------------------------------------------


class TestNormalizeNullTypes:
    def test_string_null_array_becomes_nullable_string(self):
        result = _normalize_null_types({"type": ["string", "null"]})
        assert result["type"] == "string"
        assert result["nullable"] is True

    def test_null_only_becomes_object(self):
        result = _normalize_null_types({"type": ["null"]})
        assert result["type"] == "object"

    def test_non_null_type_unchanged(self):
        result = _normalize_null_types({"type": "string"})
        assert result["type"] == "string"
        assert "nullable" not in result

    def test_nested_properties_normalized(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"]},
                "age": {"type": "integer"},
            },
        }
        result = _normalize_null_types(schema)
        assert result["properties"]["name"]["nullable"] is True
        assert result["properties"]["name"]["type"] == "string"
        assert "nullable" not in result["properties"]["age"]

    def test_nested_items_normalized(self):
        schema = {
            "type": "array",
            "items": {"type": ["string", "null"]},
        }
        result = _normalize_null_types(schema)
        assert result["items"]["nullable"] is True

    def test_non_dict_returned_unchanged(self):
        assert _normalize_null_types("string") == "string"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    def test_empty_description_returns_empty(self):
        assert _build_summary("") == ""

    def test_short_description_returned_unchanged(self):
        result = _build_summary("Do something.")
        assert result == "Do something."

    def test_first_sentence_extracted(self):
        result = _build_summary("First sentence. Second sentence.")
        assert result == "First sentence."

    def test_long_description_truncated_at_120(self):
        result = _build_summary("x" * 200)
        assert len(result) <= 120

    def test_sentence_longer_than_120_truncated(self):
        long = "A" * 130 + ". Short."
        result = _build_summary(long)
        assert len(result) <= 120

    def test_newline_as_sentence_separator(self):
        result = _build_summary("First sentence.\nSecond sentence.")
        assert result == "First sentence."


# ---------------------------------------------------------------------------
# ir_tool_to_openapi_path
# ---------------------------------------------------------------------------


class TestIrToolToOpenapiPath:
    def test_mcp_tool_produces_path(self):
        tool = Tool(name="slack", description="Slack MCP server", kind="mcp")
        path, path_item = ir_tool_to_openapi_path(tool)
        assert path == "/slack"
        assert "post" in path_item

    def test_tool_name_is_operation_id(self):
        tool = Tool(name="my_tool", description="My tool", kind="mcp")
        _, path_item = ir_tool_to_openapi_path(tool)
        assert path_item["post"]["operationId"] == "my_tool"

    def test_description_in_operation(self):
        tool = Tool(name="weather", description="Get current weather data.", kind="mcp")
        _, path_item = ir_tool_to_openapi_path(tool)
        assert "weather" in path_item["post"]["description"].lower()

    def test_tool_with_parameters(self):
        params = {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }
        tool = Tool(name="weather", description="Weather tool", kind="mcp", parameters=params)
        _, path_item = ir_tool_to_openapi_path(tool)
        body_schema = path_item["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert "city" in body_schema.get("properties", {})

    def test_tool_without_parameters_uses_empty_schema(self):
        tool = Tool(name="ping", description="Ping tool", kind="mcp")
        _, path_item = ir_tool_to_openapi_path(tool)
        body_schema = path_item["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert body_schema.get("type") == "object"

    def test_shell_tool_produces_path(self):
        tool = Tool(name="gh", description="GitHub CLI", kind="shell")
        path, path_item = ir_tool_to_openapi_path(tool)
        assert path == "/gh"
        assert "post" in path_item
