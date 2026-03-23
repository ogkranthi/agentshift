# AgentShift IR — Intermediate Representation Schema

**File:** `specs/ir-schema.json`
**Version:** 1.0
**Status:** Canonical

---

## Purpose

The IR is the universal agent model that sits between all parsers and emitters in AgentShift. Every source parser (OpenClaw, Claude Code, Copilot, Bedrock, Vertex AI) converts its native format into an IR. Every emitter converts IR into the target platform's native format.

```
OpenClaw SKILL.md  ──┐
Claude Code CLAUDE.md ─┤               ┌─► OpenClaw SKILL.md
Copilot manifest  ──┤──► IR (JSON) ──►─┤── Claude Code SKILL.md
Bedrock instruction ┤               └─► Copilot manifest
Vertex AI config   ──┘                   Bedrock instruction
```

---

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ir_version` | `"1.0"` | ✅ | Always `"1.0"` |
| `name` | string | ✅ | Slug identifier. Lowercase + hyphens. e.g. `pregnancy-companion` |
| `description` | string | ✅ | What the agent does. Used as skill trigger text in OpenClaw/Claude Code |
| `version` | string | — | Semver of this agent definition. Default `"1.0.0"` |
| `author` | string | — | Author/owner |
| `homepage` | URI | — | Docs or tool homepage |
| `persona` | object | — | System prompt + personality |
| `tools` | array | — | Capabilities available to the agent |
| `knowledge` | array | — | Knowledge sources |
| `triggers` | array | — | Cron, webhook, message, or event triggers |
| `constraints` | object | — | Platform limits and guardrails |
| `install` | array | — | Dependency install steps |
| `metadata` | object | — | Provenance and platform annotations |

---

## `persona`

The agent's system prompt and behavioral identity.

```json
{
  "persona": {
    "system_prompt": "You are a warm, knowledgeable pregnancy companion...",
    "personality_notes": "Warm and supportive. Use simple language.",
    "language": "en"
  }
}
```

| Field | Description |
|-------|-------------|
| `system_prompt` | Full instruction text passed to the model. This is the SKILL.md body (OpenClaw), CLAUDE.md content, Bedrock instruction, or Copilot system_prompt |
| `personality_notes` | Informational tone/style notes. May be embedded in system_prompt |
| `language` | BCP-47 language code. Default `"en"` |

---

## `tools[]`

Each tool the agent can invoke.

```json
{
  "tools": [
    {
      "name": "bash",
      "description": "Run shell commands on the host",
      "kind": "shell",
      "platform_availability": ["openclaw", "claude-code"]
    },
    {
      "name": "get_weather",
      "description": "Fetch current weather for a location",
      "kind": "function",
      "parameters": {
        "type": "object",
        "properties": {
          "location": { "type": "string", "description": "City name or airport code" },
          "units": { "type": "string", "enum": ["metric", "imperial"], "default": "metric" }
        },
        "required": ["location"]
      },
      "auth": {
        "type": "api_key",
        "env_var": "OPENWEATHER_API_KEY"
      }
    },
    {
      "name": "slack",
      "description": "Send and read Slack messages via the slack MCP tool",
      "kind": "mcp",
      "auth": {
        "type": "config_key",
        "config_key": "channels.slack"
      }
    }
  ]
}
```

### `Tool.kind` values

| Kind | Description | Example |
|------|-------------|---------|
| `mcp` | Model Context Protocol server | `slack`, `github` OpenClaw tools |
| `openapi` | REST/OpenAPI action group | Bedrock action groups, Copilot plugins |
| `shell` | CLI subprocess | `bash` in OpenClaw/Claude Code |
| `builtin` | Platform-native tool | `Bash`, `Read`, `WebSearch` in Claude Code |
| `function` | LLM function-calling definition | OpenAI-style function tools |
| `unknown` | Unclassified | Fallback |

---

## `knowledge[]`

Data sources the agent can read for grounding.

```json
{
  "knowledge": [
    {
      "name": "week-by-week",
      "kind": "file",
      "path": "~/.openclaw/skills/pregnancy-companion/knowledge/week-by-week.md",
      "description": "Baby development and symptoms by pregnancy week",
      "format": "markdown",
      "load_mode": "on_demand"
    },
    {
      "name": "product-docs",
      "kind": "vector_store",
      "path": "s3://my-bucket/embeddings/product-docs",
      "description": "Product documentation for RAG",
      "load_mode": "indexed"
    }
  ]
}
```

### `KnowledgeSource.load_mode` values

| Mode | Description |
|------|-------------|
| `always` | Inject full content into every session context |
| `on_demand` | Agent reads the file when it needs it |
| `indexed` | Content is embedded in a vector store for retrieval |

---

## `triggers[]`

When and how the agent activates automatically.

```json
{
  "triggers": [
    {
      "id": "morning-checkin",
      "kind": "cron",
      "cron_expr": "0 9 * * *",
      "message": "Good morning! Give today's pregnancy tip and check for upcoming appointments.",
      "session_target": "isolated",
      "delivery": {
        "mode": "announce",
        "channel": "telegram",
        "to": "123456789"
      },
      "enabled": true
    },
    {
      "id": "pr-opened",
      "kind": "event",
      "event_name": "pr.opened",
      "message": "A new PR was opened. Review it and post a summary.",
      "session_target": "isolated"
    }
  ]
}
```

### `Trigger.kind` values

| Kind | Description | Key Fields |
|------|-------------|------------|
| `cron` | Scheduled by time | `cron_expr` or `every` |
| `webhook` | HTTP POST from external service | `webhook_path` |
| `message` | Incoming chat message | `event_name` (optional filter) |
| `event` | Platform event | `event_name` |
| `manual` | User-initiated only | — |

---

## `constraints`

Platform limits and behavioral guardrails.

```json
{
  "constraints": {
    "supported_os": ["darwin", "linux"],
    "required_bins": ["curl"],
    "any_required_bins": ["claude", "codex"],
    "required_config_keys": ["channels.slack"],
    "guardrails": ["no-diagnose", "no-prescribe"],
    "topic_restrictions": ["financial advice", "legal advice"],
    "max_instruction_chars": 4000
  }
}
```

### Platform instruction limits

| Platform | Approx. Limit |
|----------|---------------|
| AWS Bedrock | 4,000 chars |
| Vertex AI Agent Builder | 8,000 chars |
| Microsoft Copilot | ~32,000 chars |
| OpenClaw / Claude Code | No hard limit (context window) |

---

## `install[]`

Dependency installation steps (multiple = fallback options).

```json
{
  "install": [
    {
      "id": "brew",
      "kind": "brew",
      "formula": "gh",
      "bins": ["gh"],
      "label": "Install GitHub CLI (brew)"
    },
    {
      "id": "apt",
      "kind": "apt",
      "package": "gh",
      "bins": ["gh"],
      "label": "Install GitHub CLI (apt)"
    }
  ]
}
```

---

## `metadata`

Provenance and platform-specific extensions.

```json
{
  "metadata": {
    "source_platform": "openclaw",
    "target_platforms": ["claude-code", "bedrock"],
    "created_at": "2026-03-23T10:00:00Z",
    "updated_at": "2026-03-23T10:00:00Z",
    "source_file": "~/.openclaw/skills/weather/SKILL.md",
    "emoji": "☔",
    "tags": ["weather", "productivity"],
    "platform_extensions": {
      "openclaw": {
        "requires": { "bins": ["curl"] }
      },
      "bedrock": {
        "agent_id": "ABCDEF1234",
        "alias_id": "TSTALIASID"
      }
    }
  }
}
```

`platform_extensions` is a catch-all for platform-specific data that has no IR equivalent. It is preserved round-trip so no information is lost.

---

## Complete Example — pregnancy-companion

```json
{
  "ir_version": "1.0",
  "name": "pregnancy-companion",
  "description": "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey",
  "version": "1.0.0",
  "persona": {
    "system_prompt": "You are a warm, knowledgeable pregnancy companion...",
    "personality_notes": "Warm, supportive, and encouraging. Never clinical.",
    "language": "en"
  },
  "tools": [
    {
      "name": "bash",
      "description": "Read/write tracking files (symptoms, weight, appointments)",
      "kind": "shell"
    }
  ],
  "knowledge": [
    {
      "name": "week-by-week",
      "kind": "file",
      "path": "~/.openclaw/skills/pregnancy-companion/knowledge/week-by-week.md",
      "description": "Baby development and symptoms by week",
      "format": "markdown",
      "load_mode": "on_demand"
    },
    {
      "name": "nutrition",
      "kind": "file",
      "path": "~/.openclaw/skills/pregnancy-companion/knowledge/nutrition.md",
      "description": "Pregnancy nutrition guide by trimester",
      "format": "markdown",
      "load_mode": "on_demand"
    }
  ],
  "triggers": [
    {
      "id": "daily-tip",
      "kind": "cron",
      "cron_expr": "0 9 * * *",
      "message": "Give today's pregnancy tip based on the current week.",
      "session_target": "isolated",
      "delivery": {
        "mode": "announce",
        "channel": "telegram",
        "to": "123456789"
      },
      "enabled": true
    }
  ],
  "constraints": {
    "supported_os": ["darwin", "linux"],
    "guardrails": ["no-diagnose", "no-prescribe"]
  },
  "metadata": {
    "source_platform": "openclaw",
    "target_platforms": ["claude-code"],
    "created_at": "2026-03-23T00:00:00Z",
    "emoji": "🤰",
    "tags": ["health", "pregnancy"]
  }
}
```

---

## Platform Mapping Reference

| IR Field | OpenClaw | Claude Code | Copilot | Bedrock | Vertex AI |
|----------|----------|-------------|---------|---------|-----------|
| `name` | `name` (frontmatter) | `name` (frontmatter) | `name` (manifest) | Agent name | Agent display name |
| `description` | `description` (frontmatter) | `description` (frontmatter) | `description` | Agent description | Agent description |
| `persona.system_prompt` | SKILL.md body | SKILL.md body / CLAUDE.md | `system_prompt` | `instruction` | Default model settings / instruction |
| `tools[].name` | Implied by MCP server / shell cmds | Allowed tool list | Plugin actions | Action group operations | Tool definitions |
| `tools[].kind=mcp` | Tool name in conversation | MCP server config | — | — | — |
| `triggers[].cron_expr` | `openclaw cron` jobs.json | External cron + claude CLI | Scheduled invocation | EventBridge / Lambda trigger | Cloud Scheduler |
| `constraints.max_instruction_chars` | None | None | ~32k | 4,000 | 8,000 |
| `constraints.required_bins` | `metadata.openclaw.requires.bins` | Implied by tool usage | N/A | N/A | N/A |
| `knowledge[].kind=file` | SKILL.md references to files | `Read` tool + CLAUDE.md | `capabilities.localization_settings` | Knowledge base S3 source | Data store |
| `metadata.emoji` | `metadata.openclaw.emoji` | — (not natively supported) | — | — | — |
| `install[]` | `metadata.openclaw.install` | — | — | — | — |
