# MCP-to-OpenAPI Mapping Specification

**Task:** A07
**Status:** Canonical
**Version:** 1.0

---

## Overview

The Model Context Protocol (MCP) and OpenAPI serve similar roles — both describe callable tools/operations — but use different structural conventions. This spec defines the canonical mapping between MCP tool definitions and OpenAPI 3.0 operation definitions used by AgentShift when:

1. Converting IR tools with `kind=mcp` into Bedrock or Vertex AI action group schemas.
2. Implementing the `agentshift convert --mcp-to-openapi` sub-command (D11).
3. Generating stub OpenAPI schemas for MCP server introspection output.

---

## Structural Overview

### MCP Tool Definition

MCP tools are described by the `tools/list` response from an MCP server:

```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read the complete contents of a file from the file system.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "The path of the file to read"
          }
        },
        "required": ["path"]
      }
    }
  ]
}
```

| MCP field | Type | Notes |
|-----------|------|-------|
| `name` | string | Unique tool identifier. Snake_case by convention |
| `description` | string | Used by the model to decide when to call the tool |
| `inputSchema` | JSON Schema object | Always `type: object` at the root |
| `inputSchema.properties` | map | Parameter definitions |
| `inputSchema.required` | array[string] | Required parameter names |

### OpenAPI 3.0 Operation

```json
{
  "openapi": "3.0.0",
  "info": { "title": "MCPBridge", "version": "1.0.0" },
  "servers": [{ "url": "https://TODO.replace.with.real.endpoint" }],
  "paths": {
    "/read_file": {
      "post": {
        "operationId": "read_file",
        "summary": "Read the complete contents of a file from the file system.",
        "description": "Read the complete contents of a file from the file system.",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "path": {
                    "type": "string",
                    "description": "The path of the file to read"
                  }
                },
                "required": ["path"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Tool execution result",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "content": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "type": { "type": "string", "enum": ["text", "image", "resource"] },
                          "text": { "type": "string" }
                        }
                      }
                    },
                    "isError": { "type": "boolean" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Field-by-Field Mapping

### MCP → OpenAPI

| MCP field | OpenAPI field | Transformation |
|-----------|--------------|----------------|
| `tool.name` | `paths` key = `"/{tool.name}"` | Prepend `/` |
| `tool.name` | `operation.operationId` | Direct copy |
| `tool.description` | `operation.summary` | Direct copy (first 120 chars if long) |
| `tool.description` | `operation.description` | Full copy |
| `tool.inputSchema` | `requestBody.content["application/json"].schema` | Direct copy |
| `tool.inputSchema.properties` | `schema.properties` | Direct copy |
| `tool.inputSchema.required` | `schema.required` | Direct copy |
| _(implicit)_ | HTTP method = `POST` | All MCP tools map to POST |
| _(implicit)_ | `requestBody.required = true` | Always required |
| _(no equivalent)_ | `servers[0].url` | Emit `"https://TODO.replace.with.real.endpoint"` |

### OpenAPI → MCP (reverse mapping)

| OpenAPI field | MCP field | Transformation |
|--------------|-----------|----------------|
| `operation.operationId` | `tool.name` | Direct copy; fall back to path segment if missing |
| `operation.description` or `operation.summary` | `tool.description` | Prefer `description`, fall back to `summary` |
| `requestBody.content["application/json"].schema` | `tool.inputSchema` | Direct copy; ensure root is `type: object` |
| `parameters[]` (query/path) | `tool.inputSchema.properties` | Lift into inputSchema object (see §Parameters) |

---

## Parameter Handling

### OpenAPI query/path parameters → MCP inputSchema

MCP tools use a single flat `inputSchema` object. When converting **OpenAPI → MCP**, parameters must be folded into the schema:

**OpenAPI input:**
```json
{
  "parameters": [
    {
      "name": "location",
      "in": "query",
      "required": true,
      "schema": { "type": "string" },
      "description": "City name"
    },
    {
      "name": "units",
      "in": "query",
      "schema": { "type": "string", "enum": ["metric", "imperial"] }
    }
  ]
}
```

**MCP output:**
```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": { "type": "string", "description": "City name" },
      "units": { "type": "string", "enum": ["metric", "imperial"] }
    },
    "required": ["location"]
  }
}
```

Rules:
- Collect all `parameters[]` entries (query, path, header) into `inputSchema.properties`.
- Any parameter with `required: true` goes into `inputSchema.required`.
- Path parameters (`:id` style) are included with a note in their description.
- If the OpenAPI operation also has a `requestBody`, merge its `schema.properties` into `inputSchema.properties`. Request body properties take precedence on name collision.

### MCP inputSchema → OpenAPI requestBody

All MCP input is encoded as a POST body. No query/path parameters are emitted.

---

## Type Mapping

MCP inputSchema uses JSON Schema; OpenAPI 3.0 also uses JSON Schema (with minor differences). The mapping is nearly 1:1:

| JSON Schema type | OpenAPI schema | Notes |
|-----------------|---------------|-------|
| `string` | `string` | Direct |
| `number` | `number` | Direct |
| `integer` | `integer` | Direct |
| `boolean` | `boolean` | Direct |
| `array` with `items` | `array` with `items` | Direct |
| `object` with `properties` | `object` with `properties` | Direct |
| `null` | Not supported in OAS 3.0 | Use `nullable: true` on the parent field |
| `oneOf` / `anyOf` / `allOf` | Supported in OAS 3.0 | Direct (but Bedrock doesn't support — see warnings) |
| `$ref` | `$ref` (within document) | Direct if within same document |
| `enum` | `enum` | Direct |
| `format` (date, date-time, etc.) | `format` | Direct |

### Null handling

MCP tools sometimes describe nullable fields. Convert:
```json
{ "type": ["string", "null"] }
```
to:
```json
{ "type": "string", "nullable": true }
```

---

## Response Schema

MCP tools return a standard `CallToolResult` structure. The OpenAPI response schema should always reflect this:

```json
{
  "200": {
    "description": "Tool execution result",
    "content": {
      "application/json": {
        "schema": {
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
                    "description": "Content block type"
                  },
                  "text": {
                    "type": "string",
                    "description": "Text content (when type=text)"
                  },
                  "data": {
                    "type": "string",
                    "description": "Base64-encoded data (when type=image)"
                  },
                  "mimeType": {
                    "type": "string",
                    "description": "MIME type (when type=image)"
                  }
                },
                "required": ["type"]
              }
            },
            "isError": {
              "type": "boolean",
              "description": "True if the tool call resulted in an error"
            }
          },
          "required": ["content"]
        }
      }
    }
  },
  "400": {
    "description": "Invalid tool call parameters"
  },
  "500": {
    "description": "Tool execution error"
  }
}
```

---

## Multi-Tool OpenAPI Document

When converting an entire MCP server (multiple tools), emit a single OpenAPI document with all tools as separate paths:

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "MCP Bridge — filesystem",
    "description": "OpenAPI wrapper for the filesystem MCP server",
    "version": "1.0.0",
    "x-mcp-server": "filesystem"
  },
  "servers": [
    { "url": "https://TODO.replace.with.mcp.bridge.endpoint" }
  ],
  "paths": {
    "/read_file": { ... },
    "/write_file": { ... },
    "/list_directory": { ... }
  }
}
```

The `x-mcp-server` extension field is used by AgentShift to preserve the MCP server name round-trip.

---

## Naming Conventions

| Convention | Rule |
|-----------|------|
| Path | `/{tool.name}` — always snake_case with leading `/` |
| `operationId` | Same as `tool.name` — snake_case |
| `summary` | First sentence of `tool.description` (≤ 120 chars) |
| `description` | Full `tool.description` |
| Document `info.title` | `"MCP Bridge — {server_name}"` |

---

## Platform-Specific Constraints

### Bedrock

- All operations must use **POST** — already the case for MCP bridge mapping.
- No `oneOf` / `anyOf` in schemas — flatten to object or use string fallback.
- `$ref` allowed only within the same document.
- `servers` URL is ignored (Lambda routing).

### Vertex AI

- Supports GET and POST — but MCP bridge always emits POST for simplicity.
- `servers[0].url` **must** be a real, accessible HTTPS endpoint.
- Supports `$ref`, `oneOf`, `anyOf` (more permissive than Bedrock).

---

## MCP Bridge Runtime Behavior

When AgentShift generates an OpenAPI schema from MCP tools, it also emits a stub **MCP Bridge** server that:

1. Accepts POST requests at `/{tool_name}`.
2. Parses the JSON body as the tool's `inputSchema`.
3. Forwards the call to the MCP server via the MCP protocol.
4. Returns the `CallToolResult` as JSON.

This bridge is the link between the OpenAPI-based Bedrock/Vertex AI agents and the local MCP server.

### Stub bridge (Python pseudocode)

```python
# mcp_bridge.py — generated by AgentShift
# TODO: Replace with your actual MCP server URL/transport
import json
from mcp import ClientSession, StdioServerParameters

MCP_SERVER_COMMAND = "npx"
MCP_SERVER_ARGS = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"]

async def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    server_params = StdioServerParameters(command=MCP_SERVER_COMMAND, args=MCP_SERVER_ARGS)
    async with ClientSession(*server_params) as session:
        result = await session.call_tool(tool_name, arguments)
        return {
            "content": [{"type": c.type, "text": getattr(c, "text", None)} for c in result.content],
            "isError": result.isError
        }
```

---

## Complete Example — Filesystem MCP Server

### Input: MCP `tools/list` response

```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read the complete contents of a file from the file system. Handles various text encodings and provides detailed error messages if the file cannot be read.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "The path of the file to read" }
        },
        "required": ["path"]
      }
    },
    {
      "name": "write_file",
      "description": "Create a new file or completely overwrite an existing file with new content.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "The path of the file to write" },
          "content": { "type": "string", "description": "The content to write to the file" }
        },
        "required": ["path", "content"]
      }
    },
    {
      "name": "list_directory",
      "description": "Get a detailed listing of all files and directories in a specified path.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "The path of the directory to list" }
        },
        "required": ["path"]
      }
    }
  ]
}
```

### Output: OpenAPI 3.0 schema

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "MCP Bridge — filesystem",
    "description": "OpenAPI wrapper for the filesystem MCP server",
    "version": "1.0.0",
    "x-mcp-server": "filesystem"
  },
  "servers": [
    { "url": "https://TODO.replace.with.mcp.bridge.endpoint" }
  ],
  "paths": {
    "/read_file": {
      "post": {
        "operationId": "read_file",
        "summary": "Read the complete contents of a file from the file system.",
        "description": "Read the complete contents of a file from the file system. Handles various text encodings and provides detailed error messages if the file cannot be read.",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "path": { "type": "string", "description": "The path of the file to read" }
                },
                "required": ["path"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Tool execution result",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "content": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "type": { "type": "string" },
                          "text": { "type": "string" }
                        }
                      }
                    },
                    "isError": { "type": "boolean" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/write_file": {
      "post": {
        "operationId": "write_file",
        "summary": "Create a new file or completely overwrite an existing file with new content.",
        "description": "Create a new file or completely overwrite an existing file with new content.",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "path": { "type": "string", "description": "The path of the file to write" },
                  "content": { "type": "string", "description": "The content to write to the file" }
                },
                "required": ["path", "content"]
              }
            }
          }
        },
        "responses": {
          "200": { "description": "Tool execution result", "content": { "application/json": { "schema": { "$ref": "#/components/schemas/ToolResult" } } } }
        }
      }
    },
    "/list_directory": {
      "post": {
        "operationId": "list_directory",
        "summary": "Get a detailed listing of all files and directories in a specified path.",
        "description": "Get a detailed listing of all files and directories in a specified path.",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "path": { "type": "string", "description": "The path of the directory to list" }
                },
                "required": ["path"]
              }
            }
          }
        },
        "responses": {
          "200": { "description": "Tool execution result", "content": { "application/json": { "schema": { "$ref": "#/components/schemas/ToolResult" } } } }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "ToolResult": {
        "type": "object",
        "properties": {
          "content": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "type": { "type": "string", "enum": ["text", "image", "resource"] },
                "text": { "type": "string" }
              }
            }
          },
          "isError": { "type": "boolean" }
        }
      }
    }
  }
}
```

---

## IR Integration

When an IR tool has `kind=mcp`, the AgentShift Bedrock/Vertex emitters call the MCP-to-OpenAPI converter:

```python
# Pseudocode
def mcp_tool_to_openapi_path(tool: IRTool) -> tuple[str, dict]:
    """Convert an IR MCP tool to an OpenAPI path item."""
    path = f"/{tool.name}"
    operation = {
        "operationId": tool.name,
        "summary": tool.description[:120] if tool.description else tool.name,
        "description": tool.description or tool.name,
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": tool.parameters or {"type": "object", "properties": {}}
                }
            }
        },
        "responses": {"200": STANDARD_MCP_RESPONSE_SCHEMA}
    }
    return path, {"post": operation}
```

---

## Notes for the Implementing Dev (D11)

1. **Always POST** — MCP tools are function calls, not REST resources. POST conveys "do something with this input" semantics.
2. **Preserve `x-mcp-server`** in the OpenAPI `info` block — this allows the bridge to route back to the correct MCP server.
3. **`servers[0].url` is always a placeholder** — emit `https://TODO.replace.with.mcp.bridge.endpoint` and document in README.
4. **inputSchema is almost always a valid OpenAPI schema** — MCP uses JSON Schema draft 2020-12 features occasionally (e.g., `prefixItems`). Strip unsupported keywords for Bedrock; keep them for Vertex AI.
5. **`null` type** — MCP schemas sometimes use `"type": ["string", "null"]`. Convert to `"type": "string", "nullable": true` for Bedrock/Vertex compatibility.
6. **`anyOf`/`oneOf` in inputSchema** — Bedrock doesn't support these. Flatten to `type: object` with a comment; Vertex AI can keep them as-is.
7. **Use `$ref` in `components/schemas`** for the shared `ToolResult` response schema — avoids duplication across paths.
8. **`operationId` uniqueness** — MCP tool names are already unique within a server. If merging multiple servers, prefix with server name: `filesystem__read_file`.
9. **Empty inputSchema** — some MCP tools have no parameters (`"inputSchema": {"type": "object", "properties": {}}`). This is valid; emit it as-is.
10. **Round-trip fidelity** — the `x-mcp-server` and original `description` fields should round-trip. Store original MCP tool JSON in `x-mcp-tool-original` extension if needed.
