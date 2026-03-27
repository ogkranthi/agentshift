# Agent Portability Format (APF)
## Specification v1.0

**Status:** Draft  
**Published:** 2026-03-27  
**Authors:** AgentShift Project  
**Repository:** https://github.com/agentshift/agentshift  
**License:** Apache 2.0  
**Feedback:** https://github.com/agentshift/agentshift/issues  

---

## Abstract

The **Agent Portability Format (APF)** is an open, vendor-neutral specification for representing AI agent definitions in a canonical intermediate form. APF enables agents to be described once and deployed to any supported runtime platform without manual reformatting. The format captures an agent's identity, behavioral instructions, tool capabilities, knowledge sources, activation triggers, and operational constraints in a single JSON document that is both human-readable and machine-processable.

This document defines APF version 1.0, its JSON Schema, normative mapping guidance for five major agent platforms, and a versioning strategy for future evolution.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Motivation and Problem Statement](#2-motivation-and-problem-statement)
3. [Design Principles](#3-design-principles)
4. [Normative Language](#4-normative-language)
5. [APF Document Structure](#5-apf-document-structure)
6. [Field Reference](#6-field-reference)
   - 6.1 [Root Fields](#61-root-fields)
   - 6.2 [persona](#62-persona)
   - 6.3 [tools](#63-tools)
   - 6.4 [knowledge](#64-knowledge)
   - 6.5 [triggers](#65-triggers)
   - 6.6 [constraints](#66-constraints)
   - 6.7 [install](#67-install)
   - 6.8 [metadata](#68-metadata)
7. [JSON Schema](#7-json-schema)
8. [Serialization Rules](#8-serialization-rules)
9. [Platform Mapping Guidance](#9-platform-mapping-guidance)
   - 9.1 [OpenClaw SKILL.md](#91-openclaw-skillmd)
   - 9.2 [Claude Code (Anthropic)](#92-claude-code-anthropic)
   - 9.3 [Microsoft 365 Copilot Declarative Agent](#93-microsoft-365-copilot-declarative-agent)
   - 9.4 [Amazon Bedrock Agents](#94-amazon-bedrock-agents)
   - 9.5 [Google Vertex AI Agent Builder](#95-google-vertex-ai-agent-builder)
   - 9.6 [LangGraph](#96-langgraph)
10. [Lossless Round-Trip Guarantee](#10-lossless-round-trip-guarantee)
11. [Versioning Strategy](#11-versioning-strategy)
12. [Security Considerations](#12-security-considerations)
13. [Conformance](#13-conformance)
14. [Examples](#14-examples)
15. [Acknowledgements](#15-acknowledgements)
16. [Change Log](#16-change-log)

---

## 1. Introduction

AI agents — autonomous software entities that perceive inputs, reason, and take actions — are becoming a primary interface through which organizations deploy AI capabilities. Unlike traditional software, agents are increasingly defined as *configuration artifacts*: a combination of behavioral instructions (system prompt), tool access, knowledge grounding, and invocation conditions.

Despite this shared conceptual model, every major agent platform uses an incompatible representation format. A developer who builds an agent for OpenClaw must rewrite it by hand to deploy it on AWS Bedrock or Microsoft Copilot. Knowledge, constraints, and tool definitions must be re-expressed in each platform's native idiom, introducing transcription errors and maintenance burden.

The **Agent Portability Format (APF)** solves this by defining a common intermediate representation (IR) that any parser can read and any emitter can write. Tool vendors, open-source projects, and standards bodies can implement APF support to make their agents portable without coordinating bilateral format agreements.

APF is implemented as the core IR of [AgentShift](https://github.com/agentshift/agentshift), an open-source tool for converting agents between platforms. This specification is published as a standalone document to enable independent implementation and potential adoption as an industry standard.

---

## 2. Motivation and Problem Statement

### 2.1 The Fragmentation Problem

As of 2026, the major agent platforms each define their own format:

| Platform | Native Format | Description |
|----------|--------------|-------------|
| OpenClaw | SKILL.md | Markdown with YAML frontmatter + free-form body |
| Claude Code (Anthropic) | SKILL.md + CLAUDE.md | Markdown skill definition |
| Microsoft 365 Copilot | declarative-agent.json | JSON manifest referencing action plugins |
| Amazon Bedrock Agents | Instruction text + OpenAPI + CloudFormation | Multi-file configuration |
| Google Vertex AI Agent Builder | agent.json | JSON configuration object |
| LangGraph | Python (StateGraph API) + langgraph.json | Code + deployment manifest |

These formats differ in:
- **Structure**: JSON, YAML frontmatter, Markdown, Python code
- **Instruction length**: 4,000 chars (Bedrock) to unlimited (OpenClaw)
- **Tool definition**: OpenAPI, MCP, Python decorator, JSON function spec
- **Trigger semantics**: cron (OpenClaw), EventBridge (Bedrock), Power Automate (Copilot)
- **Persistence**: checkpointers (LangGraph), knowledge bases (Bedrock), none (Claude Code)

### 2.2 Why a New Format?

Existing standards solve adjacent problems but do not address agent portability:

- **OpenAPI** describes REST APIs, not agent behaviors or instruction prompts
- **MCP (Model Context Protocol)** defines how tools are exposed to models but not agent identity or deployment config
- **OASF (Open Agent Schema Framework)** focuses on agent discovery and capabilities at runtime, not deployment-time portability
- **AgentCard (A2A Protocol)** provides agent identity for agent-to-agent communication but not cross-platform deployment

APF fills the deployment-time portability gap: given an APF document, a toolchain can generate the native artifacts for any supported platform.

### 2.3 Use Cases

- **Migration**: Move an agent from one platform to another without hand-rewrites
- **Multi-platform deployment**: Deploy the same agent logic to three cloud platforms from a single source of truth
- **Backup and versioning**: Store agent definitions in VCS in a stable, platform-neutral format
- **Toolchain integration**: CI/CD pipelines that emit platform-native configs from APF source
- **Marketplace**: An agent registry where developers publish once and buyers deploy anywhere

---

## 3. Design Principles

**P1 — Semantic fidelity over syntactic convenience**  
APF captures agent *semantics* — what an agent does, what it can access, how it behaves — not the syntax of any particular platform. This ensures that a semantically equivalent agent can be reconstructed on any target even when syntactic forms differ.

**P2 — Lossless by default via escape hatches**  
Every APF document can represent all information from any supported source platform without discarding data. Platform-specific fields that have no APF equivalent are preserved in `metadata.platform_extensions` and round-tripped faithfully.

**P3 — Conservative mapping over silent innovation**  
When converting between platforms, APF tooling MUST NOT silently discard or fabricate data. If a field cannot be mapped, the output MUST include a prominent `# TODO` comment or warning rather than emitting a default value that may be incorrect.

**P4 — Human-readability**  
APF documents are JSON but should be comprehensible to a developer reading them without a tool. Names are descriptive, structure is flat where possible, and the canonical form uses 2-space indentation with sorted keys.

**P5 — Minimal required surface**  
Only `ir_version`, `name`, and `description` are required. All other fields are optional. A minimal valid APF document describes an agent with a name and a description, with no tools, no triggers, and no system prompt.

**P6 — Stable identifiers**  
`name` is the stable identifier across platform representations of the same agent. It MUST be a lowercase slug suitable for use as a directory name, package name, or deployment ID on any platform.

**P7 — Version-first extensibility**  
The `ir_version` field governs schema compatibility. New required fields are never added to existing version numbers. Breaking changes increment the major version. Non-breaking additions increment the minor version.

---

## 4. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

A conformant **APF producer** is any software that emits APF documents. A conformant **APF consumer** is any software that reads APF documents and produces platform-native artifacts.

---

## 5. APF Document Structure

An APF document is a UTF-8 encoded JSON object. The file extension is `.apf.json` when stored as a standalone file. APF documents MAY also be embedded in larger formats (e.g., CI/CD pipeline configs) as inline JSON objects.

### 5.1 Minimal Valid Document

```json
{
  "ir_version": "1.0",
  "name": "my-agent",
  "description": "An agent that answers questions about the weather."
}
```

### 5.2 Full Structure Overview

```
{
  "ir_version": string,           // required
  "name": string,                 // required
  "description": string,          // required
  "version": string,              // optional
  "author": string,               // optional
  "homepage": URI,                // optional
  "persona": {                    // optional
    "system_prompt": string,
    "personality_notes": string,
    "language": string
  },
  "tools": [ Tool ],              // optional
  "knowledge": [ KnowledgeSource ], // optional
  "triggers": [ Trigger ],        // optional
  "constraints": { ... },         // optional
  "install": [ InstallStep ],     // optional
  "metadata": { ... }             // optional
}
```

---

## 6. Field Reference

### 6.1 Root Fields

#### `ir_version` (required)

**Type:** string (const)  
**Value:** `"1.0"`  
**Description:** The APF schema version this document conforms to. Always `"1.0"` for this revision. Consumers MUST reject documents with unknown `ir_version` values unless they implement forward-compatibility handling.

```json
{ "ir_version": "1.0" }
```

#### `name` (required)

**Type:** string  
**Pattern:** `^[a-z0-9][a-z0-9-]*[a-z0-9]$`  
**Max length:** 64 characters  
**Description:** Stable, lowercase slug identifier for the agent. Used as a directory name, package name, and deployment ID. MUST be unique within a registry or organization. Hyphens are the only allowed separator.

```json
{ "name": "pregnancy-companion" }
```

#### `description` (required)

**Type:** string  
**Max length:** 1,000 characters  
**Description:** Human-readable summary of what the agent does and when to invoke it. Used as the skill trigger description in OpenClaw and Claude Code, and as the agent description in cloud platforms. SHOULD be one to three sentences.

```json
{ "description": "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates." }
```

#### `version` (optional)

**Type:** string  
**Pattern:** `^\d+\.\d+\.\d+$`  
**Default:** `"1.0.0"`  
**Description:** Semantic version of this agent definition. RECOMMENDED to follow [SemVer 2.0.0](https://semver.org/).

#### `author` (optional)

**Type:** string  
**Description:** Author or organization responsible for this agent definition.

#### `homepage` (optional)

**Type:** URI string  
**Description:** URL for the agent's documentation, source repository, or home page.

---

### 6.2 `persona`

The `persona` object contains the agent's behavioral identity — the system prompt and related style guidance.

```json
{
  "persona": {
    "system_prompt": "You are a warm, knowledgeable pregnancy companion...",
    "personality_notes": "Warm and supportive. Use simple language. Never clinical.",
    "language": "en"
  }
}
```

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `system_prompt` | string | No | The full instruction prompt passed to the model at session start. This is the primary behavioral specification. |
| `personality_notes` | string | No | Informational prose describing tone, style, and personality. May be embedded in `system_prompt` at the discretion of the author. |
| `language` | string | No | BCP-47 language code for primary response language. Default: `"en"`. |

**Mapping note:** `system_prompt` is the most important field in the persona. It maps to: the SKILL.md body (OpenClaw), the CLAUDE.md file (Claude Code), the `system_prompt` field (Copilot), the `instruction` field (Bedrock), and the model instruction (Vertex AI).

---

### 6.3 `tools`

The `tools` array describes capabilities the agent can invoke — external APIs, shell commands, MCP servers, or platform-native tool calls.

```json
{
  "tools": [
    {
      "name": "get_weather",
      "description": "Get current weather for a location",
      "kind": "function",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "City name or airport code"
          },
          "units": {
            "type": "string",
            "enum": ["metric", "imperial"],
            "default": "metric"
          }
        },
        "required": ["location"]
      },
      "auth": {
        "type": "api_key",
        "env_var": "OPENWEATHER_API_KEY"
      }
    }
  ]
}
```

#### Tool Object Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Tool identifier. Used as the function name in LLM APIs. |
| `description` | string | **Yes** | What this tool does and when to use it. This text is shown to the LLM. |
| `kind` | string (enum) | No | Tool protocol. See `Tool.kind` values below. Default: `"unknown"`. |
| `parameters` | JSON Schema object | No | JSON Schema (draft-07 `object` type) describing input parameters. |
| `auth` | ToolAuth object | No | Authentication requirements. |
| `endpoint` | string | No | For `openapi`: base URL. For `mcp`: server URI or command string. |
| `platform_availability` | string[] | No | Platform slugs where this tool is available. Empty = all platforms. |

#### `Tool.kind` Values

| Value | Description | Example |
|-------|-------------|---------|
| `mcp` | Model Context Protocol server | `@modelcontextprotocol/server-brave-search` |
| `openapi` | REST/OpenAPI action group | Bedrock action group, Copilot plugin |
| `shell` | CLI subprocess | `bash`, `curl` invocations |
| `builtin` | Platform-native tool (not portable) | `Bash`, `Read`, `WebSearch` in Claude Code |
| `function` | LLM function-calling definition | OpenAI/Anthropic function tools |
| `unknown` | Unclassified | Fallback for tools that don't fit above |

#### ToolAuth Object

| Field | Type | Description |
|-------|------|-------------|
| `type` | enum | Auth mechanism: `none`, `api_key`, `oauth2`, `bearer`, `basic`, `config_key` |
| `env_var` | string | Environment variable holding the credential |
| `config_key` | string | Platform config key (OpenClaw-specific) |
| `scopes` | string[] | OAuth2 scopes required |
| `notes` | string | Human-readable auth setup instructions |

---

### 6.4 `knowledge`

The `knowledge` array describes data sources the agent uses for grounding — files, directories, URLs, vector stores, or databases.

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
    }
  ]
}
```

#### KnowledgeSource Object Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Logical name for this source. |
| `kind` | string (enum) | **Yes** | Storage type: `file`, `directory`, `url`, `vector_store`, `database`, `s3` |
| `path` | string | No | File path, directory path, or URI. `~` expands to the user's home directory. |
| `description` | string | No | What this source contains. |
| `format` | string (enum) | No | Content format: `markdown`, `json`, `yaml`, `text`, `pdf`, `html`, `unknown` |
| `load_mode` | string (enum) | No | When to access: `always`, `on_demand`, `indexed`. Default: `on_demand` |

#### `load_mode` Semantics

| Mode | Behavior |
|------|----------|
| `always` | Inject full content into every session context window |
| `on_demand` | Make available as a tool; agent reads when it determines it needs to |
| `indexed` | Content is embedded in a vector store; retrieved via semantic search |

---

### 6.5 `triggers`

The `triggers` array describes conditions that activate the agent autonomously — schedules, webhooks, platform events, or incoming messages.

```json
{
  "triggers": [
    {
      "id": "morning-checkin",
      "kind": "cron",
      "cron_expr": "0 9 * * *",
      "message": "Good morning! Give today's pregnancy tip.",
      "session_target": "isolated",
      "delivery": {
        "mode": "announce",
        "channel": "telegram",
        "to": "123456789"
      },
      "enabled": true
    }
  ]
}
```

#### Trigger Object Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | No | Unique trigger identifier within this document. |
| `kind` | string (enum) | **Yes** | Trigger type: `cron`, `webhook`, `message`, `event`, `manual` |
| `cron_expr` | string | Conditional | Standard 5-field cron expression. Required when `kind = "cron"` and `every` is absent. |
| `every` | string | Conditional | Human shorthand for schedule: `"30m"`, `"2h"`, `"1d"`. Alternative to `cron_expr`. |
| `message` | string | No | Prompt injected when the trigger fires. |
| `webhook_path` | string | No | URL path for webhook triggers. e.g. `"/webhooks/github"` |
| `event_name` | string | No | Platform event name. e.g. `"pr.opened"` |
| `delivery` | TriggerDelivery | No | Where to send the trigger's output. |
| `session_target` | string (enum) | No | Session context: `"isolated"`, `"main"`, `"thread"`. Default: `"isolated"` |
| `enabled` | boolean | No | Whether the trigger is active. Default: `true` |

#### TriggerDelivery Object

| Field | Type | Description |
|-------|------|-------------|
| `mode` | enum | Output mode: `announce`, `silent`, `reply` |
| `channel` | string (enum) | Delivery channel: `telegram`, `slack`, `discord`, `email`, `webhook`, `stdout` |
| `to` | string | Destination: chat_id, channel_id, email address, etc. |
| `account_id` | string | Platform account identifier for multi-account setups. |

---

### 6.6 `constraints`

The `constraints` object specifies platform limits, system requirements, and behavioral guardrails.

```json
{
  "constraints": {
    "supported_os": ["darwin", "linux"],
    "required_bins": ["curl", "gh"],
    "any_required_bins": ["claude", "codex"],
    "required_config_keys": ["channels.slack"],
    "guardrails": ["no-diagnose", "no-prescribe"],
    "topic_restrictions": ["financial advice", "legal advice"],
    "max_instruction_chars": 4000
  }
}
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `max_instruction_chars` | integer | Maximum character length of the system prompt. Informs emitters to truncate or warn. |
| `supported_os` | string[] | Operating systems: `darwin`, `linux`, `windows`. |
| `required_bins` | string[] | CLI binaries that MUST be present (all required). |
| `any_required_bins` | string[] | At least one of these binaries must be present. |
| `required_config_keys` | string[] | Platform config keys that must be configured (OpenClaw-specific). |
| `guardrails` | string[] | Named safety guardrails. e.g. `["no-diagnose", "no-prescribe"]` |
| `topic_restrictions` | string[] | Topics the agent must not discuss. |

---

### 6.7 `install`

The `install` array describes how to install the agent's binary or package dependencies. Each entry is one installation method; multiple entries provide fallback options for different environments.

```json
{
  "install": [
    {
      "id": "brew",
      "kind": "brew",
      "formula": "gh",
      "bins": ["gh"],
      "label": "Install GitHub CLI (Homebrew)"
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

#### InstallStep Object Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | **Yes** | Unique ID for this install method within the array. |
| `kind` | string (enum) | **Yes** | Package manager: `brew`, `apt`, `go`, `npm`, `pip`, `cargo`, `script`, `manual` |
| `formula` | string | Conditional | Homebrew formula name. Required when `kind = "brew"`. |
| `package` | string | Conditional | Package name for `apt`, `npm`, `pip`, `cargo`. |
| `module` | string | Conditional | Go module path. e.g. `"github.com/cli/cli/cmd/gh@latest"`. Required when `kind = "go"`. |
| `script_url` | URI | Conditional | URL for `curl | sh` install scripts. Required when `kind = "script"`. |
| `bins` | string[] | No | Binary names installed by this step. |
| `label` | string | No | Human-readable label for this option. |

---

### 6.8 `metadata`

The `metadata` object stores provenance information, platform annotations, and extension data. All fields are optional.

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

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_platform` | string (enum) | Platform this APF document was originally parsed from. |
| `target_platforms` | string[] | Platforms this document is intended to be emitted to. |
| `created_at` | ISO 8601 datetime | When this APF document was first created. |
| `updated_at` | ISO 8601 datetime | When this APF document was last modified. |
| `source_file` | string | Path or URI of the original source file. |
| `emoji` | string | Display emoji for the agent. |
| `tags` | string[] | Arbitrary classification tags. |
| `platform_extensions` | object | Platform-specific data keyed by platform slug. Preserved round-trip. |

**Platform slug values:** `openclaw`, `claude-code`, `copilot`, `bedrock`, `vertex-ai`, `langgraph`

---

## 7. JSON Schema

The normative JSON Schema for APF v1.0 is published at:

```
https://agentshift.dev/schemas/apf/v1.json
```

The schema file (`specs/ir-schema.json` in the AgentShift repository) is the authoritative source. In case of conflict between this prose specification and the JSON Schema, the JSON Schema governs.

### 7.1 Schema Validation

Conformant APF producers MUST emit documents that validate against the APF v1.0 JSON Schema. Conformant APF consumers SHOULD validate incoming documents and MUST report a clear error for documents that fail validation.

### 7.2 Partial Compliance

A document that omits all optional fields and provides only the three required fields (`ir_version`, `name`, `description`) is a valid APF v1.0 document. Consumers MUST accept minimally valid documents without error.

---

## 8. Serialization Rules

**Encoding:** APF documents MUST be encoded as UTF-8.

**Indentation:** The canonical form uses 2-space indentation. Tools SHOULD normalize to canonical form when writing; they MUST NOT reject non-canonical indentation when reading.

**Key ordering:** The canonical form uses the key order specified in this document (root fields in § 6.1 order, then `persona`, `tools`, `knowledge`, `triggers`, `constraints`, `install`, `metadata`). Tools MUST NOT reject documents with non-canonical key ordering.

**Null vs. absent:** A field with value `null` is semantically equivalent to the field being absent. Producers SHOULD omit fields rather than setting them to `null`. Consumers MUST treat `null` values as equivalent to the field being absent.

**Empty arrays:** A field with value `[]` is semantically equivalent to the field being absent for array-typed fields. Producers SHOULD omit empty arrays.

**String whitespace:** Leading and trailing whitespace in string values is significant and MUST be preserved.

**URI validation:** Fields declared as URI type MUST be absolute URIs (scheme + host + path). Relative URIs are not permitted in URI fields.

---

## 9. Platform Mapping Guidance

This section provides normative mapping guidance for APF producers and consumers targeting each supported platform. The word "MUST" applies to all conformant implementations; "SHOULD" indicates a strong recommendation; "MAY" indicates an option.

### 9.1 OpenClaw SKILL.md

**Format:** Markdown with YAML frontmatter  
**Platform slug:** `openclaw`  
**Spec reference:** `specs/openclaw-skill-format.md`

#### APF → SKILL.md (Emitter)

| APF Field | SKILL.md Output |
|-----------|----------------|
| `name` | `name:` frontmatter field |
| `description` | `description:` frontmatter field |
| `version` | `version:` frontmatter field |
| `author` | `author:` frontmatter field |
| `persona.system_prompt` | Markdown body of SKILL.md |
| `persona.language` | Comment in body: `<!-- Language: {lang} -->` |
| `tools[].kind = "mcp"` | Tool reference in prose body |
| `tools[].kind = "builtin"` | Permitted tool in body prose |
| `knowledge[].path` | File path referenced in body |
| `triggers[]` | `openclaw cron` job definition (via `jobs.json` or prose) |
| `constraints.supported_os` | `os:` frontmatter field |
| `constraints.required_bins` | `metadata.openclaw.requires.bins` |
| `constraints.any_required_bins` | `metadata.openclaw.requires.anyBins` |
| `install[]` | `metadata.openclaw.install` array |
| `metadata.emoji` | `metadata.openclaw.emoji` |

#### SKILL.md → APF (Parser)

| SKILL.md Field | APF Field |
|---------------|-----------|
| `name:` frontmatter | `name` |
| `description:` frontmatter | `description` |
| Markdown body | `persona.system_prompt` |
| `os:` frontmatter | `constraints.supported_os` |
| `metadata.openclaw.requires.bins` | `constraints.required_bins` |
| `metadata.openclaw.emoji` | `metadata.emoji` |
| `metadata.openclaw.install` | `install[]` |

**Constraint:** The `tools[].kind = "openapi"` field has no direct representation in OpenClaw SKILL.md and SHOULD be preserved in `metadata.platform_extensions.openclaw`.

---

### 9.2 Claude Code (Anthropic)

**Format:** SKILL.md (skill description) + CLAUDE.md (behavioral instructions) + `.claude/settings.json` (permissions)  
**Platform slug:** `claude-code`  
**Spec reference:** `specs/claude-code-format.md`

#### APF → Claude Code (Emitter)

| APF Field | Claude Code Output |
|-----------|-------------------|
| `name` | `name:` in SKILL.md frontmatter |
| `description` | `description:` in SKILL.md frontmatter |
| `persona.system_prompt` | CLAUDE.md body |
| `persona.personality_notes` | Comment in CLAUDE.md |
| `tools[].kind = "builtin"` | Allowed tool in `.claude/settings.json` permissions |
| `tools[].kind = "mcp"` | MCP server entry in settings |
| `tools[].kind = "shell"` | Bash tool permission in settings |
| `knowledge[].path` | `Read` tool permission for path in settings |
| `constraints.required_bins` | CLAUDE.md prerequisites section |
| `metadata.emoji` | SKILL.md frontmatter if field exists |

#### Claude Code → APF (Parser)

| Claude Code Field | APF Field |
|------------------|-----------|
| SKILL.md `name:` | `name` |
| SKILL.md `description:` | `description` |
| CLAUDE.md body | `persona.system_prompt` |
| `.claude/settings.json` tool permissions | `tools[]` with inferred `kind` |

---

### 9.3 Microsoft 365 Copilot Declarative Agent

**Format:** `declarative-agent.json` + optional `manifest.json` (Teams App)  
**Platform slug:** `copilot`  
**Spec reference:** `specs/m365-declarative-agent-format.md`

#### APF → Copilot (Emitter)

| APF Field | Copilot Manifest Field |
|-----------|----------------------|
| `name` | `name` |
| `description` | `description` |
| `persona.system_prompt` | `instructions` |
| `tools[].kind = "openapi"` | `actions[].file` (OpenAPI plugin) |
| `knowledge[].kind = "url"` | `capabilities[].sources[].url` (Web Search) |
| `knowledge[].kind = "file"` | SharePoint URL reference |
| `constraints.topic_restrictions` | Copilot Studio guardrail configuration |

**Length constraint:** `instructions` field accepts approximately 32,000 characters. If `persona.system_prompt` exceeds this, the emitter MUST truncate and MUST emit a warning.

#### Copilot → APF (Parser)

| Copilot Field | APF Field |
|--------------|-----------|
| `name` | `name` |
| `description` | `description` |
| `instructions` | `persona.system_prompt` |
| `actions[]` | `tools[]` with `kind = "openapi"` |

---

### 9.4 Amazon Bedrock Agents

**Format:** Instruction text + OpenAPI schema (JSON) + CloudFormation YAML  
**Platform slug:** `bedrock`  
**Spec reference:** `specs/bedrock-agent-format.md`

#### APF → Bedrock (Emitter)

| APF Field | Bedrock Output |
|-----------|---------------|
| `name` | `AgentName` in CloudFormation resource |
| `description` | `Description` in CloudFormation |
| `persona.system_prompt` | `Instruction` field (max 4,000 chars) |
| `tools[].kind = "openapi"` | Action group with `ApiSchema` referencing OpenAPI file |
| `tools[].kind = "function"` | Action group with function definition |
| `knowledge[].kind = "vector_store"` | Knowledge base S3 data source |
| `knowledge[].kind = "s3"` | Knowledge base S3 data source |
| `constraints.topic_restrictions` | Bedrock Guardrails topic policy |
| `constraints.guardrails` | Bedrock Guardrails content filters |

**Critical length constraint:** `Instruction` field MUST NOT exceed 4,000 characters. If `persona.system_prompt` exceeds this limit, the emitter MUST truncate to 4,000 chars and MUST emit a prominent warning. The emitter SHOULD attempt intelligent truncation (e.g., preserve the first and last paragraphs and truncate the middle).

#### Bedrock → APF (Parser)

| Bedrock Field | APF Field |
|--------------|-----------|
| `AgentName` | `name` (slug-normalized) |
| `Instruction` | `persona.system_prompt` |
| Action group operations | `tools[]` |
| Knowledge base sources | `knowledge[]` |

---

### 9.5 Google Vertex AI Agent Builder

**Format:** JSON `agent.json` configuration  
**Platform slug:** `vertex-ai`  
**Spec reference:** `specs/vertex-ai-agent-format.md`

#### APF → Vertex AI (Emitter)

| APF Field | Vertex AI Output |
|-----------|----------------|
| `name` | `displayName` |
| `description` | `description` |
| `persona.system_prompt` | Default model instruction / system instruction |
| `tools[].kind = "openapi"` | Tool definition with OpenAPI spec |
| `tools[].kind = "function"` | Tool definition with function schema |
| `knowledge[].kind = "vector_store"` | Data store reference |
| `constraints.topic_restrictions` | Safety filters configuration |

**Length constraint:** System instruction field accepts approximately 8,000 characters. Emitters SHOULD warn if `persona.system_prompt` exceeds this.

#### Vertex AI → APF (Parser)

| Vertex AI Field | APF Field |
|----------------|-----------|
| `displayName` | `name` (slug-normalized) |
| `description` | `description` |
| System instruction | `persona.system_prompt` |
| Tool definitions | `tools[]` |

---

### 9.6 LangGraph

**Format:** Python (StateGraph API) + `langgraph.json` deployment manifest  
**Platform slug:** `langgraph`  
**Spec reference:** `specs/langgraph-agent-format.md`

#### APF → LangGraph (Emitter)

| APF Field | LangGraph Output |
|-----------|----------------|
| `name` | Package directory name (`name.replace("-", "_")`) |
| `description` | README.md heading, module docstring |
| `version` | `__version__` in `__init__.py` |
| `persona.system_prompt` | `SystemMessage(content=SYSTEM_PROMPT)` in `nodes.py` |
| `tools[].kind = "function"` | `@tool`-decorated function in `tools.py` |
| `tools[].kind = "mcp"` | `load_mcp_tools()` configuration |
| `tools[].kind = "openapi"` | `requests`-based `@tool` wrapper |
| `tools[].auth.env_var` | `os.environ["ENV_VAR"]` in tool body |
| `knowledge[].load_mode = "on_demand"` | `@tool` exposing file/URL content |
| `knowledge[].load_mode = "always"` | Content injected into system prompt |
| `triggers[].kind = "cron"` | `schedule` library example in README |
| `constraints.guardrails` | Additional instructions appended to system prompt |
| Deployment | `langgraph.json` manifest |

The emitter MUST produce a runnable Python package with the structure defined in `specs/langgraph-agent-format.md § 10`.

#### LangGraph → APF (Parser)

Parsing LangGraph agents is complex because they are defined in code. A parser SHOULD support:
- Extracting `SystemMessage` content as `persona.system_prompt`
- Inferring `tools[]` from `@tool`-decorated functions
- Reading `langgraph.json` for package metadata

Full LangGraph → APF round-trip is NOT REQUIRED for v1.0 conformance.

---

## 10. Lossless Round-Trip Guarantee

A conformant APF toolchain MUST support lossless round-trips for the following path:

```
Platform A native format
    → APF (parse)
    → Platform A native format (emit)
```

The output after one round-trip MUST be semantically equivalent to the input (same behavior, same tools, same knowledge, same triggers). It NEED NOT be byte-for-byte identical (whitespace, ordering, comments may differ).

For cross-platform conversions (Platform A → APF → Platform B):

- Fields that map directly MUST be mapped
- Fields that have no equivalent on Platform B MUST be preserved in `metadata.platform_extensions` for the source platform
- Fields that Platform B requires but are absent from the APF document MAY be populated with reasonable defaults, but the emitter MUST document clearly which defaults were applied

The `metadata.platform_extensions` mechanism is the APF round-trip guarantee: any platform-specific data that cannot be expressed in the APF schema is stored here and recovered when emitting back to the original platform.

---

## 11. Versioning Strategy

### 11.1 Version Number Scheme

APF uses **Semantic Versioning** for the `ir_version` field:

- **Major version** (`2.0`, `3.0`): Breaking changes — fields renamed, removed, or retyped; schema changes that invalidate existing documents
- **Minor version** (`1.1`, `1.2`): Non-breaking additions — new optional fields, new enum values, new platform mappings
- **Patch version**: Not used. Patch-level changes (documentation, examples, clarifications) do not increment `ir_version`.

### 11.2 Current Version

The current version is `1.0`. All APF documents with `ir_version: "1.0"` MUST conform to this specification.

### 11.3 Compatibility Policy

- **Backward compatibility:** A v1.1 consumer MUST accept v1.0 documents without error.
- **Forward compatibility:** A v1.0 consumer encountering a v1.1 document SHOULD accept it and ignore unknown fields (per JSON Schema `additionalProperties` rules). A v1.0 consumer MUST NOT silently lose data from v1.1 documents.
- **Major version incompatibility:** A v1.x consumer receiving a v2.0 document MUST reject it with a clear error message citing the version mismatch.

### 11.4 Deprecation Policy

Fields are deprecated with a two-version grace period:
1. Field is marked `deprecated` in the schema with a `deprecationMessage`
2. Field is removed in the next major version
3. Producers SHOULD warn when writing deprecated fields
4. Consumers MUST continue to accept deprecated fields during the grace period

### 11.5 Extension Mechanism

Before a field is standardized, it MAY be expressed in `metadata.platform_extensions` under an informal namespace. Once a field achieves broad adoption across multiple platforms, it becomes a candidate for promotion to a first-class APF field via the minor version process.

### 11.6 Schema Publication

Each version's normative JSON Schema is published at a stable URL:

```
https://agentshift.dev/schemas/apf/v{major}.{minor}.json
https://agentshift.dev/schemas/apf/v{major}.json  (latest minor)
https://agentshift.dev/schemas/apf/latest.json     (latest stable)
```

Historical versions are retained indefinitely. The `$id` field in each schema is the canonical URL for that version.

---

## 12. Security Considerations

### 12.1 System Prompt Injection

The `persona.system_prompt` field is user-controlled content that is passed directly to an LLM. APF producers and consumers MUST treat this field as untrusted when the APF document originates from an external source.

Implementations SHOULD:
- Validate that `system_prompt` does not contain embedded instructions intended to override safety guardrails
- Log warnings when `system_prompt` contains patterns associated with prompt injection attacks
- Provide an option to sandbox or strip `system_prompt` content

### 12.2 Tool Endpoint Exposure

The `tools[].endpoint` field may contain internal service URLs, including URLs with embedded credentials. APF documents containing such URLs MUST NOT be committed to public version control systems.

Implementations SHOULD:
- Validate that endpoint URLs do not contain credentials (username:password@host patterns)
- Support environment variable substitution in endpoint fields for production deployments

### 12.3 Credential Storage

`tools[].auth.env_var` refers to an environment variable name, not a credential value. APF documents MUST NOT contain credential values. Implementations MUST enforce this by rejecting documents where auth fields contain credential values rather than references.

### 12.4 `platform_extensions` Arbitrary Data

The `metadata.platform_extensions` field accepts arbitrary JSON objects. Implementations MUST NOT execute or evaluate content from this field. It is a passthrough container only.

### 12.5 Install Script URLs

`install[].script_url` contains URLs for `curl | sh` install scripts. Implementations that execute install steps SHOULD verify script integrity (e.g., checksum validation) before execution and SHOULD warn users before executing arbitrary remote scripts.

---

## 13. Conformance

### 13.1 Conformance Levels

This specification defines two conformance classes:

**Class 1 — APF Producer**  
Software that reads agent definitions from a native platform format and emits APF documents. A conformant Class 1 implementation:
- MUST emit documents that validate against the APF v1.0 JSON Schema
- MUST populate `ir_version`, `name`, and `description`
- MUST map all source platform fields that have a defined APF equivalent
- MUST preserve unmappable fields in `metadata.platform_extensions`
- MUST NOT discard information silently

**Class 2 — APF Consumer**  
Software that reads APF documents and emits native platform artifacts. A conformant Class 2 implementation:
- MUST accept any document that validates against the APF v1.0 JSON Schema
- MUST map all APF fields that have a defined equivalent on the target platform
- MUST emit a `# TODO` comment or structured warning for fields it cannot map
- MUST NOT fabricate values for fields not present in the source APF document (except for mandatory platform fields with defined defaults)

### 13.2 Test Suite

A reference test suite is maintained at `tests/` in the AgentShift repository. Conformant implementations are encouraged to run this suite and publish their results.

---

## 14. Examples

### 14.1 Minimal Agent

```json
{
  "ir_version": "1.0",
  "name": "hello-world",
  "description": "A simple agent that greets the user."
}
```

### 14.2 Tool-Heavy Agent (Weather)

```json
{
  "ir_version": "1.0",
  "name": "weather",
  "description": "Get current weather and forecasts via wttr.in or Open-Meteo.",
  "version": "1.0.0",
  "author": "AgentShift Examples",
  "persona": {
    "system_prompt": "You are a helpful weather assistant. Use the available tools to provide accurate, up-to-date weather information for any location the user asks about.",
    "language": "en"
  },
  "tools": [
    {
      "name": "get_weather",
      "description": "Get current weather for a location",
      "kind": "function",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "City name or airport code"
          },
          "units": {
            "type": "string",
            "enum": ["metric", "imperial"],
            "default": "metric",
            "description": "Temperature units"
          }
        },
        "required": ["location"]
      },
      "auth": {
        "type": "api_key",
        "env_var": "OPENWEATHER_API_KEY",
        "notes": "Get a free key at https://openweathermap.org/api"
      }
    }
  ],
  "constraints": {
    "required_bins": ["curl"],
    "supported_os": ["darwin", "linux", "windows"]
  },
  "metadata": {
    "source_platform": "openclaw",
    "target_platforms": ["claude-code", "bedrock", "copilot", "vertex-ai", "langgraph"],
    "created_at": "2026-03-23T00:00:00Z",
    "emoji": "☔",
    "tags": ["weather", "productivity", "utility"]
  }
}
```

### 14.3 Knowledge-Heavy Agent (Pregnancy Companion)

```json
{
  "ir_version": "1.0",
  "name": "pregnancy-companion",
  "description": "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey",
  "version": "1.0.0",
  "persona": {
    "system_prompt": "You are a warm, knowledgeable pregnancy companion. You provide evidence-based information about pregnancy, development stages, nutrition, and symptoms. You are supportive and encouraging, but always recommend consulting a healthcare provider for medical decisions.\n\nNEVER diagnose conditions. NEVER prescribe treatments. ALWAYS recommend professional medical advice for concerning symptoms.",
    "personality_notes": "Warm, supportive, and encouraging. Never clinical.",
    "language": "en"
  },
  "tools": [
    {
      "name": "read_tracking_file",
      "description": "Read the user's symptom or weight tracking file",
      "kind": "shell",
      "platform_availability": ["openclaw", "claude-code"]
    }
  ],
  "knowledge": [
    {
      "name": "week-by-week",
      "kind": "file",
      "path": "~/.openclaw/skills/pregnancy-companion/knowledge/week-by-week.md",
      "description": "Baby development and maternal symptoms by pregnancy week",
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
      "message": "Good morning! Give today's pregnancy tip based on the current week.",
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
    "guardrails": ["no-diagnose", "no-prescribe"],
    "topic_restrictions": ["medical diagnosis", "prescription drugs"]
  },
  "metadata": {
    "source_platform": "openclaw",
    "target_platforms": ["claude-code"],
    "created_at": "2026-03-23T00:00:00Z",
    "emoji": "🤰",
    "tags": ["health", "pregnancy", "companion"]
  }
}
```

### 14.4 Platform Mapping Table (Summary)

| APF Field | OpenClaw | Claude Code | Copilot | Bedrock | Vertex AI | LangGraph |
|-----------|----------|-------------|---------|---------|-----------|-----------|
| `name` | `name:` frontmatter | `name:` frontmatter | `name` | Agent name | `displayName` | Package name |
| `description` | `description:` | `description:` | `description` | Description | `description` | README |
| `persona.system_prompt` | SKILL.md body | CLAUDE.md body | `instructions` | `instruction` (≤4k chars) | System instruction (≤8k) | `SystemMessage` in nodes.py |
| `tools[function]` | Prose reference | Allowed tools | Plugin action | Action group | Tool definition | `@tool` in tools.py |
| `tools[mcp]` | Tool reference | MCP config | Not supported | Not supported | Not supported | `load_mcp_tools()` |
| `triggers[cron]` | `openclaw cron` | External cron | Power Automate | EventBridge | Cloud Scheduler | `schedule` library |
| `knowledge[file]` | File reference | `Read` permission | Capability source | S3 knowledge base | Data store | `@tool` file reader |
| `constraints.guardrails` | Manual enforcement | CLAUDE.md note | Copilot Studio | Bedrock Guardrails | Safety filters | System prompt append |

---

## 15. Acknowledgements

APF was developed as part of the [AgentShift](https://github.com/agentshift/agentshift) open-source project. The format is inspired by:

- [OpenAPI Specification](https://spec.openapis.org/) — for its approach to describing API surfaces in a vendor-neutral format
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — for pioneering tool protocol standardization
- [Open Agent Schema Framework (OASF)](https://oasf.ai/) — for demonstrating the value of agent capability schemas
- [Cloud Native Application Bundle (CNAB)](https://cnab.io/) — for its approach to portable application packaging

The following individuals contributed to the design of APF v1.0: the AgentShift autonomous build crew (Chief, Architect, Dev, Tester).

---

## 16. Change Log

### v1.0 (2026-03-27)

- Initial release
- Defines core schema: root fields, `persona`, `tools`, `knowledge`, `triggers`, `constraints`, `install`, `metadata`
- Platform mapping guidance for: OpenClaw, Claude Code, Microsoft 365 Copilot, Amazon Bedrock, Google Vertex AI, LangGraph
- Normative JSON Schema at `specs/ir-schema.json`
- Establishes versioning strategy and conformance classes

---

*Agent Portability Format Specification v1.0*  
*© 2026 AgentShift Project. Licensed under Apache 2.0.*  
*https://agentshift.dev*
