# A2A Agent Card Format Spec

**Spec ID:** A16
**Status:** Canonical
**Author:** @architect
**Closes:** A16 (Week 8 backlog)
**Source:** [A2A Protocol Specification](https://a2a-protocol.org) (Linux Foundation / Google)
**Implements:** D27

---

## 1. Overview

The A2A (Agent-to-Agent) protocol defines a standard for inter-agent communication. The **Agent Card**
is a JSON document that describes an agent's identity, capabilities, skills, and authentication
requirements. It is served at a well-known URL for discovery by other agents and clients.

AgentShift will emit Agent Cards from IR to enable agents to participate in A2A ecosystems.

**Serving location:**
```
https://{agent-domain}/.well-known/agent-card.json
```

This follows RFC 8615. Clients `GET` this URL to discover the agent.

**Extended Agent Card:** An authenticated endpoint (`GET /extendedAgentCard`) may return a richer
card when `capabilities.extendedAgentCard` is `true`.

---

## 2. Agent Card JSON Structure

### 2.1 Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | yes | Human-readable agent name |
| `description` | `string` | yes | What the agent does |
| `version` | `string` | yes | Agent version (semver). Example: `"1.0.0"` |
| `supportedInterfaces` | `AgentInterface[]` | yes | Ordered list of endpoints/protocols; first is preferred |
| `capabilities` | `AgentCapabilities` | yes | Supported A2A features |
| `defaultInputModes` | `string[]` | yes | Accepted media types (e.g., `["text/plain"]`) |
| `defaultOutputModes` | `string[]` | yes | Produced media types |
| `skills` | `AgentSkill[]` | yes | Skills the agent can perform (at least one) |
| `provider` | `AgentProvider` | no | Service provider details |
| `securitySchemes` | `map<string, SecurityScheme>` | no | Named security scheme definitions (OpenAPI 3.2 style) |
| `securityRequirements` | `SecurityRequirement[]` | no | Security requirements for contacting the agent |
| `documentationUrl` | `string` (URI) | no | URL to additional docs |
| `iconUrl` | `string` (URI) | no | URL to an icon |
| `signatures` | `AgentCardSignature[]` | no | JWS signatures for card integrity (RFC 7515) |

---

## 3. `AgentInterface`

Each entry describes an endpoint where the agent is reachable.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | `string` (URI) | yes | Absolute HTTPS URL of the interface |
| `protocolBinding` | `string` | yes | `"JSONRPC"`, `"GRPC"`, `"HTTP+JSON"`, or custom |
| `protocolVersion` | `string` | yes | A2A protocol version (e.g., `"1.0"`) |
| `tenant` | `string` | no | Tenant ID for multi-tenant deployments |

---

## 4. `AgentCapabilities`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `streaming` | `boolean` | no | Whether agent supports SSE streaming responses |
| `pushNotifications` | `boolean` | no | Whether agent supports push notifications for async task updates |
| `extendedAgentCard` | `boolean` | no | Whether agent provides an authenticated extended card |
| `extensions` | `AgentExtension[]` | no | Custom capability extensions |

### 4.1 `AgentExtension`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uri` | `string` | yes | Unique URI identifying the extension (should include version) |
| `description` | `string` | no | Human-readable description |
| `required` | `boolean` | no | If `true`, client MUST understand this extension |
| `params` | `object` | no | Extension-specific configuration |

---

## 5. `AgentSkill[]`

Each skill represents a discrete capability the agent can perform.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` | yes | Unique skill identifier |
| `name` | `string` | yes | Human-readable name |
| `description` | `string` | yes | Detailed description of the skill |
| `tags` | `string[]` | yes | Keywords for categorization/discovery (at least one) |
| `examples` | `string[]` | no | Example prompts or scenarios |
| `inputModes` | `string[]` | no | Override of `defaultInputModes` for this skill |
| `outputModes` | `string[]` | no | Override of `defaultOutputModes` for this skill |
| `securityRequirements` | `SecurityRequirement[]` | no | Skill-specific security requirements |

---

## 6. `AgentProvider`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `organization` | `string` | yes | Provider organization name (e.g., `"Google"`) |
| `url` | `string` (URI) | yes | Provider website URL |

---

## 7. `AgentAuthentication` — Security Schemes

`securitySchemes` is a map of named security scheme definitions. Each value is one of:

### 7.1 API Key (`apiKeySecurityScheme`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `location` | `string` | yes | `"query"`, `"header"`, or `"cookie"` |
| `name` | `string` | yes | Name of the parameter |
| `description` | `string` | no | Description |

### 7.2 HTTP Auth (`httpAuthSecurityScheme`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scheme` | `string` | yes | HTTP auth scheme (e.g., `"Bearer"`, `"Basic"`) |
| `bearerFormat` | `string` | no | Token format hint (e.g., `"JWT"`) |
| `description` | `string` | no | Description |

### 7.3 OAuth 2.0 (`oauth2SecurityScheme`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `flows` | `OAuthFlows` | yes | OAuth flow definitions |
| `oauth2MetadataUrl` | `string` | no | RFC 8414 auth server metadata URL |
| `description` | `string` | no | Description |

**OAuth flow types:**
- `authorizationCode`: `authorizationUrl`, `tokenUrl`, `refreshUrl`, `scopes`, `pkceRequired`
- `clientCredentials`: `tokenUrl`, `refreshUrl`, `scopes`
- `deviceCode`: `deviceAuthorizationUrl`, `tokenUrl`, `refreshUrl`, `scopes`

### 7.4 OpenID Connect (`openIdConnectSecurityScheme`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `openIdConnectUrl` | `string` | yes | OIDC Discovery URL |
| `description` | `string` | no | Description |

### 7.5 Mutual TLS (`mtlsSecurityScheme`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `string` | no | Description |

### 7.6 `SecurityRequirement`

A map of scheme name → required scopes:
```json
{ "bearerAuth": ["read", "write"] }
```

---

## 8. IR → A2A Agent Card Mapping

### 8.1 Core field mapping

| IR Field | A2A Field | Transformation |
|----------|-----------|----------------|
| `ir.name` | `name` | Direct |
| `ir.description` | `description` | Direct |
| `ir.version` | `version` | Direct (default `"1.0.0"`) |
| `ir.author` | `provider.organization` | Use as org name; if absent, use `"Unknown"` |
| `ir.homepage` | `provider.url` | Direct; if absent, use `documentationUrl` or omit `provider` |
| `ir.homepage` | `documentationUrl` | Direct |
| `ir.metadata.emoji` | _(not mapped)_ | No A2A equivalent |
| `ir.metadata.tags` | _(distributed)_ | Used as skill `tags` |

### 8.2 Tools → Skills mapping

Each IR tool maps to an `AgentSkill`:

```python
AgentSkill(
    id=tool.name,
    name=tool.name.replace("_", " ").title(),
    description=tool.description,
    tags=ir.metadata.tags or [tool.kind],
    examples=[],
    inputModes=None,    # inherit defaults
    outputModes=None,   # inherit defaults
)
```

**Grouping strategy (alternative):** If the agent has many tools, group related tools into a
single skill:
- All `shell` + `builtin` file tools → one "File Operations" skill
- All `mcp` tools → one skill per MCP server
- All `function`/`openapi` tools → one skill per tool

The emitter should support both strategies via a `--skill-strategy` flag (`per-tool` or `grouped`).

### 8.3 Persona → description enrichment

If `ir.persona.system_prompt` is present, the emitter MAY include a summary in the agent
`description` field. The full system prompt is NOT included in the Agent Card (it is an internal
implementation detail, not meant for external discovery).

If `ir.persona.personality_notes` is present, append to the agent `description`.

### 8.4 Triggers → capabilities

| IR Trigger kind | A2A Capability |
|-----------------|----------------|
| Any trigger present | `streaming: true` (agent can push updates) |
| `kind=webhook` | `pushNotifications: true` |
| `kind=event` | `pushNotifications: true` |
| `kind=cron` | _(not mapped — internal scheduling)_ |

### 8.5 Governance → custom extension

Governance has no native A2A equivalent. The emitter should express governance metadata via an
`AgentExtension`:

```json
{
  "capabilities": {
    "extensions": [
      {
        "uri": "https://agentshift.sh/extensions/governance/v1",
        "description": "Agent governance constraints (guardrails, tool permissions, platform annotations)",
        "required": false,
        "params": {
          "guardrail_count": 2,
          "tool_permission_count": 1,
          "platform_annotation_count": 1,
          "guardrail_categories": ["safety", "privacy"],
          "summary": "This agent has safety and privacy guardrails. Use 'agentshift audit' for full governance details."
        }
      }
    ]
  }
}
```

### 8.6 Auth mapping

| IR `ToolAuth.type` | A2A Security Scheme |
|---------------------|---------------------|
| `api_key` | `apiKeySecurityScheme` with `location: "header"`, `name: "Authorization"` |
| `bearer` | `httpAuthSecurityScheme` with `scheme: "Bearer"` |
| `oauth2` | `oauth2SecurityScheme` with appropriate flow |
| `basic` | `httpAuthSecurityScheme` with `scheme: "Basic"` |
| `none` | _(no securitySchemes)_ |
| `config_key` | _(not mapped — internal config)_ |

If any tools require auth, emit the security scheme and add a `securityRequirements` entry.

### 8.7 Interface defaults

The emitter generates a placeholder `supportedInterfaces` entry:

```json
{
  "supportedInterfaces": [
    {
      "url": "https://TODO.example.com/a2a/v1",
      "protocolBinding": "HTTP+JSON",
      "protocolVersion": "1.0"
    }
  ]
}
```

The user must update the URL to their actual deployment endpoint.

### 8.8 Default modes

```json
{
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"]
}
```

If the agent has knowledge sources with `format: "json"`, add `"application/json"` to input modes.

---

## 9. Complete Field Mapping Table

| IR Field | A2A Field | Notes |
|----------|-----------|-------|
| `name` | `name` | Direct |
| `description` | `description` | Direct; may be enriched with persona notes |
| `version` | `version` | Direct |
| `author` | `provider.organization` | Best-effort |
| `homepage` | `provider.url`, `documentationUrl` | Both set if available |
| `persona.system_prompt` | _(not exposed)_ | Internal; not in Agent Card |
| `persona.personality_notes` | `description` (appended) | Appended to description |
| `tools[]` | `skills[]` | One skill per tool (or grouped) |
| `tools[].name` | `skills[].id` | Direct |
| `tools[].description` | `skills[].description` | Direct |
| `knowledge[]` | _(not mapped)_ | Internal implementation detail |
| `triggers[]` | `capabilities.streaming`/`pushNotifications` | Inferred |
| `constraints.guardrails` | _(not mapped)_ | Legacy field; use `governance` |
| `governance` | `capabilities.extensions[]` | Custom extension |
| `install[]` | _(not mapped)_ | Deployment concern, not discovery |
| `metadata.tags` | `skills[].tags` | Distributed across skills |
| `metadata.emoji` | `iconUrl` | Could generate SVG icon; otherwise omit |
| `metadata.source_platform` | _(not mapped)_ | Internal provenance |

---

## 10. Example Output — Simple Agent

### Input IR (weather agent):
```json
{
  "name": "weather",
  "description": "Get current weather and forecasts via wttr.in",
  "version": "1.0.0",
  "tools": [
    {
      "name": "get_weather",
      "description": "Fetch current weather for a location",
      "kind": "function"
    }
  ]
}
```

### Output Agent Card:
```json
{
  "name": "weather",
  "description": "Get current weather and forecasts via wttr.in",
  "version": "1.0.0",
  "supportedInterfaces": [
    {
      "url": "https://TODO.example.com/a2a/v1",
      "protocolBinding": "HTTP+JSON",
      "protocolVersion": "1.0"
    }
  ],
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [
    {
      "id": "get_weather",
      "name": "Get Weather",
      "description": "Fetch current weather for a location",
      "tags": ["weather", "function"]
    }
  ]
}
```

---

## 11. Example Output — Pregnancy Companion

### Input IR:
```json
{
  "name": "pregnancy-companion",
  "description": "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates",
  "version": "1.0.0",
  "author": "OpenClaw",
  "homepage": "https://agentshift.sh",
  "tools": [
    { "name": "bash", "description": "Read/write tracking files", "kind": "shell" },
    { "name": "slack", "description": "Send Slack messages", "kind": "mcp" }
  ],
  "triggers": [
    { "kind": "cron", "id": "daily-tip", "cron_expr": "0 9 * * *" }
  ],
  "governance": {
    "guardrails": [
      { "id": "G001", "text": "Never provide medical diagnoses.", "category": "safety", "severity": "critical" },
      { "id": "G002", "text": "Do not share PII.", "category": "privacy", "severity": "high" }
    ],
    "tool_permissions": [
      { "tool_name": "bash", "access": "read-only" }
    ]
  },
  "metadata": {
    "tags": ["health", "pregnancy"],
    "emoji": "\ud83e\udd30"
  }
}
```

### Output Agent Card:
```json
{
  "name": "pregnancy-companion",
  "description": "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates",
  "version": "1.0.0",
  "supportedInterfaces": [
    {
      "url": "https://TODO.example.com/a2a/v1",
      "protocolBinding": "HTTP+JSON",
      "protocolVersion": "1.0"
    }
  ],
  "provider": {
    "organization": "OpenClaw",
    "url": "https://agentshift.sh"
  },
  "documentationUrl": "https://agentshift.sh",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "extensions": [
      {
        "uri": "https://agentshift.sh/extensions/governance/v1",
        "description": "Agent governance constraints (guardrails, tool permissions)",
        "required": false,
        "params": {
          "guardrail_count": 2,
          "tool_permission_count": 1,
          "platform_annotation_count": 0,
          "guardrail_categories": ["safety", "privacy"],
          "summary": "This agent has safety and privacy guardrails. Use 'agentshift audit' for details."
        }
      }
    ]
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [
    {
      "id": "bash",
      "name": "Bash",
      "description": "Read/write tracking files",
      "tags": ["health", "pregnancy", "shell"]
    },
    {
      "id": "slack",
      "name": "Slack",
      "description": "Send Slack messages",
      "tags": ["health", "pregnancy", "mcp"]
    }
  ]
}
```

---

## 12. Emitter Entry Point

The emitter is implemented in `src/agentshift/emitters/a2a.py`.

```python
def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write an A2A Agent Card JSON from an AgentIR.

    Outputs:
    - agent-card.json (the Agent Card)
    - README.md (deployment instructions)
    """
```

---

## 13. CLI Integration

```bash
# Convert IR to A2A Agent Card
agentshift convert agent.json --to a2a --output /tmp/a2a-output

# Convert OpenClaw skill to A2A
agentshift convert ~/.openclaw/skills/weather --from openclaw --to a2a

# Diff IR against an existing Agent Card
agentshift diff agent.json --from ir ./agent-card.json --from a2a
```

---

## 14. Limitations and Future Work

| IR Capability | A2A Support | Notes |
|---------------|-------------|-------|
| `persona.system_prompt` | Not exposed | System prompts are internal — not for discovery |
| `knowledge[]` | Not mapped | Internal data sources |
| `triggers[kind=cron]` | Not mapped | Internal scheduling |
| `install[]` | Not mapped | Deployment concern |
| `constraints` | Not mapped | Internal limits |
| `governance` (full) | Extension only | Governance summary via custom extension |
| `metadata.emoji` | `iconUrl` (partial) | Could generate SVG; otherwise lost |

**Future enhancements:**
- A2A parser (reverse direction: Agent Card → IR) for discovering and importing external agents
- Support for `extendedAgentCard` to expose additional metadata after authentication
- Skill grouping strategies configurable via CLI flags
- Integration with A2A registries for agent discovery and publishing

---

## Appendix A — A2A Protocol Summary

| Aspect | Detail |
|--------|--------|
| **Repo** | `a2aproject/A2A` (Linux Foundation, contributed by Google) |
| **Spec version** | 1.0.0 |
| **Transport** | JSON-RPC 2.0 over HTTP(S), gRPC, or HTTP+JSON |
| **Content type** | `application/a2a+json` |
| **Discovery** | `/.well-known/agent-card.json` (RFC 8615) |
| **Signing** | JWS (RFC 7515) for Agent Card integrity |
| **Caching** | Standard HTTP caching (Cache-Control, ETag) recommended |

---

## Appendix B — IR `ToolAuth` → A2A Security Scheme Mapping

```python
def _map_auth(ir: AgentIR) -> dict:
    """Build securitySchemes from IR tool auth."""
    schemes = {}
    for tool in ir.tools:
        if not tool.auth or tool.auth.type == "none":
            continue
        if tool.auth.type == "api_key":
            schemes[f"{tool.name}_api_key"] = {
                "apiKeySecurityScheme": {
                    "location": "header",
                    "name": tool.auth.env_var or "Authorization",
                }
            }
        elif tool.auth.type == "bearer":
            schemes[f"{tool.name}_bearer"] = {
                "httpAuthSecurityScheme": {
                    "scheme": "Bearer",
                }
            }
        elif tool.auth.type == "oauth2":
            schemes[f"{tool.name}_oauth2"] = {
                "oauth2SecurityScheme": {
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "https://TODO.example.com/oauth/token",
                            "scopes": {s: s for s in (tool.auth.scopes or [])},
                        }
                    }
                }
            }
        elif tool.auth.type == "basic":
            schemes[f"{tool.name}_basic"] = {
                "httpAuthSecurityScheme": {
                    "scheme": "Basic",
                }
            }
    return schemes
```
