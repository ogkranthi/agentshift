"""MCP-to-OpenAPI converter — converts MCP tool definitions to OpenAPI 3.0 schemas."""

from __future__ import annotations

from typing import Any

# Standard MCP response schema used for all tool results
_MCP_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {
            "type": "array",
            "description": "Result content blocks",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["text", "image", "resource"],
                        "description": "Content block type",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content (when type=text)",
                    },
                    "data": {
                        "type": "string",
                        "description": "Base64-encoded data (when type=image)",
                    },
                    "mimeType": {
                        "type": "string",
                        "description": "MIME type (when type=image)",
                    },
                },
                "required": ["type"],
            },
        },
        "isError": {
            "type": "boolean",
            "description": "True if the tool call resulted in an error",
        },
    },
    "required": ["content"],
}

_TOOL_RESULT_COMPONENT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["text", "image", "resource"]},
                    "text": {"type": "string"},
                },
            },
        },
        "isError": {"type": "boolean"},
    },
}


def _normalize_null_types(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert JSON Schema null union types to OpenAPI nullable style.

    e.g. {"type": ["string", "null"]} → {"type": "string", "nullable": true}
    """
    if not isinstance(schema, dict):
        return schema

    result = dict(schema)

    # Handle ["string", "null"] style type arrays
    if isinstance(result.get("type"), list):
        types = result["type"]
        non_null = [t for t in types if t != "null"]
        if "null" in types:
            result["nullable"] = True
        if len(non_null) == 1:
            result["type"] = non_null[0]
        elif len(non_null) == 0:
            result["type"] = "object"
        # else leave as list — Vertex AI can handle it

    # Recurse into properties
    if "properties" in result and isinstance(result["properties"], dict):
        result["properties"] = {
            k: _normalize_null_types(v) for k, v in result["properties"].items()
        }

    # Recurse into items
    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _normalize_null_types(result["items"])

    return result


def _build_summary(description: str) -> str:
    """Extract first sentence (≤ 120 chars) as summary."""
    if not description:
        return ""
    # First sentence or first 120 chars
    for sep in (". ", ".\n"):
        idx = description.find(sep)
        if 0 < idx < 120:
            return description[: idx + 1]
    return description[:120]


def _mcp_tool_to_path_item(tool: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Convert a single MCP tool dict to an (path, path_item) tuple."""
    name: str = tool["name"]
    description: str = tool.get("description") or name
    input_schema: dict[str, Any] = tool.get("inputSchema") or {
        "type": "object",
        "properties": {},
    }

    # Normalize null types in input schema
    input_schema = _normalize_null_types(input_schema)

    path = f"/{name}"
    operation: dict[str, Any] = {
        "operationId": name,
        "summary": _build_summary(description),
        "description": description,
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": input_schema,
                }
            },
        },
        "responses": {
            "200": {
                "description": "Tool execution result",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ToolResult"},
                    }
                },
            },
            "400": {"description": "Invalid tool call parameters"},
            "500": {"description": "Tool execution error"},
        },
    }
    path_item = {"post": operation}
    return path, path_item


def mcp_to_openapi(
    mcp_tools: list[dict[str, Any]],
    server_name: str = "mcp",
    title: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Convert a list of MCP tool definitions to an OpenAPI 3.0 schema.

    Args:
        mcp_tools: List of MCP tool dicts with keys: name, description, inputSchema.
        server_name: Name of the MCP server (used in info.title and x-mcp-server).
        title: Override for info.title. Defaults to "MCP Bridge — {server_name}".
        description: Override for info.description.

    Returns:
        An OpenAPI 3.0 schema dict.
    """
    resolved_title = title or f"MCP Bridge — {server_name}"
    resolved_description = (
        description or f"OpenAPI wrapper for the {server_name} MCP server"
    )

    paths: dict[str, Any] = {}
    for tool in mcp_tools:
        path, path_item = _mcp_tool_to_path_item(tool)
        paths[path] = path_item

    schema: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {
            "title": resolved_title,
            "description": resolved_description,
            "version": "1.0.0",
            "x-mcp-server": server_name,
        },
        "servers": [{"url": "https://TODO.replace.with.mcp.bridge.endpoint"}],
        "paths": paths,
        "components": {
            "schemas": {
                "ToolResult": _TOOL_RESULT_COMPONENT,
            }
        },
    }
    return schema


def ir_tool_to_openapi_path(tool: Any) -> tuple[str, dict[str, Any]]:
    """Convert an IR Tool with kind=mcp to an OpenAPI path item.

    Used by the Bedrock/Vertex emitters to include MCP tools in action group schemas.
    """
    mcp_dict = {
        "name": tool.name,
        "description": tool.description or tool.name,
        "inputSchema": tool.parameters or {"type": "object", "properties": {}},
    }
    return _mcp_tool_to_path_item(mcp_dict)
