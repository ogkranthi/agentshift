# Vertex AI → IR Parser Spec

**Spec ID:** A14
**Status:** Canonical
**Author:** @architect
**Closes:** A14 (Week 7 backlog)
**Reverse of:** `specs/vertex-ai-agent-format.md` (emitter direction)
**Implements:** D23

---

## 1. Overview

The Vertex AI parser converts GCP Vertex AI Agent Builder artifacts back into an AgentShift IR.
This is the reverse of the Vertex AI emitter (`src/agentshift/emitters/vertex.py`).

**Input artifacts** (any combination; parser must be tolerant of missing files):

| File | Role | Required? |
|------|------|-----------|
| `agent.json` | Agent resource definition (AgentShift-generated or API export) | **Primary** |
| `tools.json` | Tool definitions array (AgentShift-generated) | Tool extraction |
| `README.md` | Deployment documentation (optional, for stub detection) | Optional |

**Primary input format:** `agent.json` (AgentShift-generated or Vertex AI API response).

---

## 2. Input Format Reference

### 2.1 `agent.json` — AgentShift-generated

The format produced by `src/agentshift/emitters/vertex.py`:

```json
{
  "displayName": "Pregnancy Companion",
  "goal": "You are a warm, knowledgeable pregnancy companion...",
  "instructions": [
    "Never diagnose medical conditions or prescribe treatments.",
    "Respond in a warm, supportive, non-clinical tone."
  ],
  "tools": [
    {
      "name": "symptom-tracker",
      "type": "FUNCTION",
      "description": "Log and retrieve pregnancy symptoms.",
      "x-agentshift-stub": "Implement as Cloud Function or Cloud Run service"
    }
  ],
  "defaultLanguageCode": "en",
  "supportedLanguageCodes": ["en"]
}
```

### 2.2 `agent.json` — Vertex AI API response (Reasoning Engine / Agent Builder)

The Vertex AI API returns agents in this format:

```json
{
  "name": "projects/my-project/locations/us-central1/agents/12345",
  "displayName": "Pregnancy Companion",
  "goal": "You are a warm, knowledgeable pregnancy companion...",
  "instructions": [
    "Never diagnose medical conditions.",
    "Always recommend consulting a doctor."
  ],
  "tools": [
    {
      "name": "projects/my-project/locations/us-central1/agents/12345/tools/tool-id"
    }
  ],
  "defaultLanguageCode": "en",
  "supportedLanguageCodes": ["en"],
  "createTime": "2024-01-15T10:30:00Z",
  "updateTime": "2024-01-20T14:22:00Z"
}
```

### 2.3 `tools.json` — AgentShift-generated tool definitions

The format produced by the AgentShift Vertex emitter:

```json
[
  {
    "displayName": "SymptomTracker",
    "description": "Log and retrieve pregnancy symptoms",
    "functionDeclarations": [
      {
        "name": "log_symptom",
        "description": "Log a pregnancy symptom",
        "parameters": {
          "type": "object",
          "properties": {
            "symptom": { "type": "string" },
            "severity": { "type": "integer" }
          }
        }
      }
    ]
  },
  {
    "displayName": "PregnancyKnowledgeBase",
    "description": "Search pregnancy guides",
    "datastoreSpec": {
      "datastoreType": "UNSTRUCTURED_DOCUMENTS",
      "dataStores": ["projects/MY_PROJECT/locations/us-central1/collections/default_collection/dataStores/pregnancy-kb"]
    }
  }
]
```

---

## 3. Vertex AI → IR Field Mapping

### 3.1 Core fields

| Vertex AI field | IR field | Transformation |
|-----------------|----------|----------------|
| `displayName` | `name` | Slugify: `"Pregnancy Companion"` → `"pregnancy-companion"` |
| `goal` | `persona.system_prompt` | Direct; also run section extractor |
| `instructions` | Combined with `goal` into `persona.system_prompt` | See §3.2 |
| `defaultLanguageCode` | `persona.language` | Direct (BCP-47) |
| `description` (if present) | `description` | Direct |
| `createTime` | `metadata.created_at` | ISO 8601 |
| `updateTime` | `metadata.updated_at` | ISO 8601 |
| `name` (full resource path) | `metadata.platform_extensions.vertex.resource_name` | Preserve |

**`description` fallback:** If `description` is absent in the Vertex config, derive it from the
first sentence of `goal`. Truncate at 200 chars.

### 3.2 `goal` + `instructions` → `persona.system_prompt`

The Vertex emitter splits content between `goal` (from `sections.overview`) and `instructions`
(from `sections.behavior`, `sections.persona`, etc.). The parser must reconstruct the unified
`system_prompt` from both.

**Reconstruction algorithm:**

1. Start with `goal` as the base of `system_prompt`.
2. If `instructions` is non-empty, append a separator and join the instruction lines:
   ```
   {goal}

   ---

   {instructions[0]}
   {instructions[1]}
   ...
   ```
3. Run `extract_sections()` on the combined text. If sections are detected, populate
   `persona.sections`.

**Section recovery from instructions:**

The Vertex emitter produces structured instruction lines with headings like `"Behavior:\n..."`.
The parser SHOULD recognize the `"SectionName:\n..."` pattern and attempt to restore sections:

```python
# Pattern: "Heading:\ncontent"
section_pattern = re.compile(r'^([A-Z][a-zA-Z\s-]+):\n(.+)', re.MULTILINE | re.DOTALL)
```

If `"Restrictions:\n..."` is found in instructions, extract as `sections["guardrails"]`.

### 3.3 Platform metadata

```python
ir.metadata.source_platform = "vertex"
ir.metadata.platform_extensions["vertex"] = {
    "resource_name": resource_name,       # Full resource path if available
    "display_name": display_name,         # Original displayName (before slugification)
    "model": model_override,              # From platform_extensions.vertex_ai.model if set
}
```

### 3.4 Tools from `agent.json`

The AgentShift Vertex emitter embeds tools directly in `agent.json` (not separate tool resources).
Parse each entry in the `tools` array:

**Case 1: Inline tool with `type` field (AgentShift-generated):**
```python
Tool(
    name=tool["name"],
    description=tool.get("description", ""),
    kind=_infer_kind(tool),
)
```

**Kind inference from `type` field:**
| `type` value | IR `kind` |
|-------------|-----------|
| `"FUNCTION"` | `"function"` (or `"shell"` / `"mcp"` if `x-agentshift-stub` is present) |
| `"OPEN_API"` | `"openapi"` |
| (absent / unknown) | `"unknown"` |

**`x-agentshift-stub` detection:**
- If `"x-agentshift-stub"` key is present → `kind="shell"` (default)
- If stub value contains `"MCP"` or `"mcp"` → `kind="mcp"`
- If stub value contains `"Cloud Function"` or `"Cloud Run"` → `kind="function"`

### 3.5 Tools from `tools.json`

When `tools.json` is present (AgentShift-generated or exported from Vertex API), parse each
tool entry:

**Case 1: Function tool (has `functionDeclarations`):**
```python
for func in tool_entry["functionDeclarations"]:
    Tool(
        name=func["name"],
        description=func.get("description", tool_entry.get("description", "")),
        kind="function",
        parameters=func.get("parameters"),
    )
```

**Case 2: OpenAPI tool (has `openApiFunctionDeclarations`):**
```python
Tool(
    name=_slugify(tool_entry["displayName"]),
    description=tool_entry.get("description", ""),
    kind="openapi",
    endpoint=_extract_server_url(tool_entry),
    parameters=None,  # Schema available in openApiFunctionDeclarations.specification
    auth=_parse_vertex_auth(tool_entry.get("authentication")),
)
```

**Case 3: Data store tool (has `datastoreSpec`):**
```python
KnowledgeSource(
    name=_slugify(tool_entry["displayName"]),
    description=tool_entry.get("description", ""),
    kind="vector_store",
    path=_extract_datastore_id(tool_entry["datastoreSpec"]),
    load_mode="indexed",
    format="unknown",
)
```
Data store tools are added to `ir.knowledge`, not `ir.tools`.

### 3.6 Auth reconstruction

For OpenAPI tools with an `authentication` block:

| Vertex auth type | IR `ToolAuth.type` | Notes |
|-----------------|-------------------|-------|
| `apiKeyConfig` | `"api_key"` | `env_var` from `apiKeyConfig.name` |
| `oauthConfig` | `"oauth2"` | `scopes` from `oauthConfig.scope` |
| `serviceAccountConfig` | `"bearer"` | `notes` = service account email |
| (absent) | `"none"` | |

### 3.7 `instructions` → L1 Guardrails (heuristic)

When `instructions` is populated, scan each instruction string for guardrail patterns using the
same heuristic as the Bedrock parser (§4 of `bedrock-parser-spec.md`):

- Patterns: `"never "`, `"do not "`, `"always "`, `"must not "`, `"avoid "`, `"prohibited"`
- Use `_infer_category()` and `_infer_severity()` utility functions (shared with Bedrock parser)
- Store results in `governance.guardrails`

The parser SHOULD also look for a `"Restrictions:"` prefix in instruction lines — these are
`sections["guardrails"]` that were linearized by the emitter and may contain explicit rules.

---

## 4. `goal` Parsing

The Vertex emitter uses `sections["overview"]` as the `goal` when `persona.sections` is
populated. The parser must reconstruct `persona.sections` from this.

**Detection:** If `goal` is a short paragraph without markdown headings, treat it as
`sections["overview"]`. Then combine with `instructions` structure to fill other sections.

**Section reconstruction from the linearized form:**

The emitter produces instructions in the pattern:
```
"Behavior:\n- Always state the location..."
"Persona:\nWarm and supportive..."
"Restrictions:\nDo not provide weather advisories as official warnings."
```

The parser should detect `"SectionName:\ncontent"` and map to sections:

| Instruction prefix | Section key |
|-------------------|-------------|
| `"Behavior:"` | `behavior` |
| `"Persona:"` | `persona` |
| `"Tools:"` | `tools` |
| `"Knowledge:"` | `knowledge` |
| `"Restrictions:"` | `guardrails` |
| (no prefix match) | Appended to `behavior` |

If section detection succeeds, populate `persona.sections` (overriding raw goal-based detection).

---

## 5. Parser Entry Point

The parser is implemented in `src/agentshift/parsers/vertex.py`.

```python
def parse(input_dir: Path) -> AgentIR:
    """Parse Vertex AI Agent Builder artifacts from a directory into an AgentIR.
    
    Reads any combination of:
    - agent.json          (required)
    - tools.json          (optional — additional tool definitions)
    - README.md           (optional — stub detection hints)
    
    At least agent.json must be present.
    """
```

**Alternative entry points:**

```python
def parse_api_response(agent_data: dict, tools_data: list[dict] | None = None) -> AgentIR:
    """Parse raw Vertex AI API response dicts."""

def parse_agent_json(agent_json: str, tools_json: str | None = None) -> AgentIR:
    """Parse from JSON strings directly."""
```

---

## 6. Input Resolution Order

When multiple files are present:

1. `agent.json` is always required.
2. `tools.json` — merge tools with `agent.json["tools"]`; `tools.json` entries take precedence
   (they have richer schemas).
3. `README.md` — scan for stub tool names to enrich kind inference.

**Tool deduplication:** If the same tool name appears in both `agent.json["tools"]` and
`tools.json`, the `tools.json` entry wins (it has the full declaration).

---

## 7. CLI Integration

```bash
# Convert from Vertex AI artifacts directory
agentshift convert ./vertex-output/ --from vertex --to openclaw

# Convert a single agent.json
agentshift convert ./agent.json --from vertex --to openclaw

# Diff: compare Vertex agent with OpenClaw skill
agentshift diff ./vertex-output/ --from vertex ./my-skill/ --from openclaw

# Audit: governance preservation when converting vertex → bedrock
agentshift audit ./vertex-output/ --from vertex --targets bedrock
```

---

## 8. Validation Notes

The parser output MUST pass `agentshift validate`. Key checks:

1. `ir.name` is non-empty and slug-safe.
2. `ir.persona.system_prompt` is non-empty.
3. `ir.description` is non-empty (derive from `goal` if absent).
4. All `tool.name` values are unique.
5. `governance.guardrails[].id` values are unique.
6. `persona.language` is a valid BCP-47 code.

---

## 9. Round-Trip Fidelity

A round-trip is: `openclaw → vertex → openclaw`.

**Guaranteed to survive:**
- Agent `name` (via displayName slugification)
- `persona.system_prompt` (goal + instructions combined)
- `persona.sections` (if instructions use `"SectionName:\n..."` pattern)
- `persona.language` (via `defaultLanguageCode`)
- Function tool names and descriptions
- Data store knowledge sources
- OpenAPI tool endpoints (if real URLs were present)

**Known lossy fields:**
- `persona.sections` partial loss — `"examples"` and `"triggers"` sections are dropped by emitter
- `tool.auth` — partially inferred from authentication blocks
- `triggers` — Cloud Scheduler stubs in README are not parsed back
- `install` — not applicable to Vertex AI
- `constraints` — not preserved
- `governance.tool_permissions` — not expressed in Vertex output; only elevated L1 text survives

**Vertex-specific lossy patterns:**
- Goal truncation: if original was > 8,000 chars, the emitter truncated it; the parser cannot
  recover the full text.
- Tool inline vs. tools.json: when the emitter puts tools in `agent.json["tools"]`, some fields
  (like full OpenAPI specs) may be lost.

---

## 10. Example Round-Trip

### Input (`agent.json` — AgentShift-generated):
```json
{
  "displayName": "weather",
  "goal": "I provide current weather and forecasts using wttr.in or Open-Meteo.",
  "instructions": [
    "Behavior:",
    "- Always state the location you're reporting for.",
    "- Use °C by default; offer °F on request.",
    "Restrictions:",
    "Do not provide weather advisories as official warnings."
  ],
  "tools": [],
  "defaultLanguageCode": "en",
  "supportedLanguageCodes": ["en"]
}
```

### Output IR:
```json
{
  "ir_version": "1.0",
  "name": "weather",
  "description": "I provide current weather and forecasts using wttr.in or Open-Meteo.",
  "persona": {
    "system_prompt": "I provide current weather and forecasts using wttr.in or Open-Meteo.\n\n---\n\nBehavior:\n- Always state the location you're reporting for.\n- Use °C by default; offer °F on request.\nRestrictions:\nDo not provide weather advisories as official warnings.",
    "sections": {
      "overview": "I provide current weather and forecasts using wttr.in or Open-Meteo.",
      "behavior": "- Always state the location you're reporting for.\n- Use °C by default; offer °F on request.",
      "guardrails": "Do not provide weather advisories as official warnings."
    },
    "language": "en"
  },
  "tools": [],
  "governance": {
    "guardrails": [
      {
        "id": "G001",
        "text": "Do not provide weather advisories as official warnings.",
        "category": "scope",
        "severity": "medium"
      }
    ],
    "tool_permissions": [],
    "platform_annotations": []
  },
  "metadata": {
    "source_platform": "vertex",
    "platform_extensions": {
      "vertex": {
        "display_name": "weather"
      }
    }
  }
}
```

---

## 11. Shared Utilities (Bedrock + Vertex)

The following utility functions are used by both the Bedrock and Vertex parsers. They SHOULD be
implemented in a shared module `src/agentshift/parsers/utils.py`:

```python
def slugify(name: str) -> str:
    """Convert display name to slug: 'Pregnancy Companion' → 'pregnancy-companion'."""
    ...

def title_case_to_slug(name: str) -> str:
    """Same as slugify — alias for clarity."""
    ...

def infer_guardrail_category(text: str) -> str:
    """Infer Guardrail.category from keywords in the text."""
    ...

def infer_guardrail_severity(text: str) -> str:
    """Infer Guardrail.severity from keywords in the text."""
    ...

def extract_guardrails_from_text(
    text: str,
    id_prefix: str = "G",
) -> list[Guardrail]:
    """Scan text for guardrail-like sentences and extract Guardrail objects."""
    ...

def is_todo_placeholder(value: str) -> bool:
    """Return True if value is a TODO/placeholder string from an AgentShift emitter."""
    return "TODO" in value or "PLACEHOLDER" in value
```

---

## Appendix A — Vertex AI API Shapes

### Agent resource (Vertex AI REST API v1beta1):
```json
{
  "name": "projects/{project}/locations/{location}/agents/{agent_id}",
  "displayName": "My Agent",
  "goal": "You are a helpful assistant.",
  "instructions": ["Always be polite."],
  "tools": [
    { "name": "projects/{project}/locations/{location}/agents/{agent_id}/tools/{tool_id}" }
  ],
  "defaultLanguageCode": "en",
  "supportedLanguageCodes": ["en"],
  "createTime": "2024-01-15T10:30:00Z",
  "updateTime": "2024-01-20T14:22:00Z"
}
```

### Tool resource (function declarations):
```json
{
  "name": "projects/{project}/locations/{location}/agents/{agent_id}/tools/{tool_id}",
  "displayName": "WeatherTool",
  "description": "Look up weather data",
  "functionDeclarations": [
    {
      "name": "get_weather",
      "description": "Get current weather for a location",
      "parameters": {
        "type": "object",
        "properties": {
          "location": { "type": "string" }
        },
        "required": ["location"]
      }
    }
  ]
}
```

### Tool resource (OpenAPI):
```json
{
  "displayName": "WeatherAPI",
  "openApiFunctionDeclarations": {
    "specification": { ... },
    "authentication": {
      "apiKeyConfig": {
        "name": "appid",
        "in": "QUERY",
        "httpElementLocation": "HTTP_IN_QUERY"
      }
    }
  }
}
```

### Tool resource (data store):
```json
{
  "displayName": "KnowledgeBase",
  "datastoreSpec": {
    "datastoreType": "UNSTRUCTURED_DOCUMENTS",
    "dataStores": [
      "projects/{project}/locations/{location}/collections/default_collection/dataStores/{ds_id}"
    ]
  }
}
```

---

## Appendix B — Tool Kind Detection Heuristic

```python
def infer_tool_kind(tool_entry: dict) -> str:
    """Infer IR tool kind from a Vertex tool dict."""
    if "datastoreSpec" in tool_entry:
        return "knowledge"   # Route to ir.knowledge, not ir.tools
    if "openApiFunctionDeclarations" in tool_entry:
        return "openapi"
    if "functionDeclarations" in tool_entry:
        return "function"
    
    # For inline tools in agent.json["tools"]
    tool_type = tool_entry.get("type", "")
    stub = tool_entry.get("x-agentshift-stub", "")
    
    if tool_type == "OPEN_API":
        return "openapi"
    if tool_type == "FUNCTION":
        if stub:
            stub_lower = stub.lower()
            if "mcp" in stub_lower:
                return "mcp"
            if "shell" in stub_lower:
                return "shell"
        return "function"
    
    return "unknown"
```
