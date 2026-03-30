# Bedrock → IR Parser Spec

**Spec ID:** A13
**Status:** Canonical
**Author:** @architect
**Closes:** A13 (Week 7 backlog)
**Reverse of:** `specs/bedrock-agent-format.md` (emitter direction)
**Implements:** D22

---

## 1. Overview

The Bedrock parser converts AWS Bedrock agent artifacts back into an AgentShift IR. This is
the reverse of the Bedrock emitter (`src/agentshift/emitters/bedrock.py`).

**Input artifacts** (any combination; parser must be tolerant of missing files):

| File | Role | Required? |
|------|------|-----------|
| `bedrock-agent.json` | Agent resource definition (from API or console export) | Primary |
| `cloudformation.yaml` | CloudFormation template (AgentShift-generated or hand-crafted) | Alternative to JSON |
| `instruction.txt` | Plain-text instruction (≤ 4,000 chars) | Supplementary |
| `openapi.json` | OpenAPI 3.0 action group schema | Tool extraction |
| `guardrail-config.json` | Guardrail configuration (AgentShift-generated) | Governance extraction |

**Primary input format:** `bedrock-agent.json` (Bedrock API response or exported config).
The parser MUST also accept `cloudformation.yaml` as the primary source (common for AgentShift
round-trips, since the emitter produces CloudFormation).

---

## 2. Input Format Reference

### 2.1 `bedrock-agent.json` — Bedrock API Agent Resource

The Bedrock API returns agents in this format (from `GetAgent` / `ListAgents` calls):

```json
{
  "agentId": "ABCD1234",
  "agentName": "pregnancy-companion",
  "agentStatus": "PREPARED",
  "agentResourceRoleArn": "arn:aws:iam::123456789012:role/BedrockAgentRole",
  "description": "24/7 pregnancy companion",
  "instruction": "You are a warm, knowledgeable pregnancy companion...",
  "foundationModel": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "idleSessionTTLInSeconds": 1800,
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-20T14:22:00Z",
  "actionGroups": [
    {
      "actionGroupId": "AG001",
      "actionGroupName": "pregnancy-companion-tracker",
      "actionGroupState": "ENABLED",
      "description": "Symptom and appointment tracking tools",
      "actionGroupExecutor": {
        "lambda": "arn:aws:lambda:us-east-1:123456789012:function:pc-tracker-handler"
      }
    }
  ],
  "knowledgeBases": [
    {
      "knowledgeBaseId": "kb-ABC123",
      "knowledgeBaseState": "ENABLED",
      "description": "Pregnancy guides and week-by-week development info"
    }
  ],
  "guardrailConfiguration": {
    "guardrailId": "G001",
    "guardrailVersion": "1"
  }
}
```

### 2.2 `cloudformation.yaml` — AgentShift-generated CloudFormation template

See `specs/bedrock-agent-format.md` §Complete CloudFormation Example. The parser must read the
`Instruction`, `Description`, `FoundationModel`, `ActionGroups`, and `KnowledgeBases` properties
from the `AWS::Bedrock::Agent` resource.

### 2.3 `instruction.txt` — Plain-text instruction

When `instruction.txt` is present alongside `bedrock-agent.json`, its content takes precedence
over the `instruction` field in the JSON (it may be the untruncated version).

### 2.4 `openapi.json` — Action group OpenAPI schema

Used to reconstruct `ir.tools` from the action group's path definitions.

### 2.5 `guardrail-config.json` — AgentShift-generated guardrail config

The format produced by the Bedrock emitter's `_build_guardrail_config()` function:
```json
{
  "topicPolicyConfig": {
    "topicsConfig": [
      {
        "name": "medical-diagnoses",
        "definition": "Never provide medical diagnoses",
        "type": "DENY"
      }
    ]
  }
}
```

---

## 3. Bedrock → IR Field Mapping

### 3.1 Core fields

| Bedrock field | IR field | Transformation |
|---------------|----------|----------------|
| `agentName` | `name` | Direct |
| `description` | `description` | Direct; empty string → use first sentence of `instruction` |
| `instruction` / `instruction.txt` | `persona.system_prompt` | Direct; strip AgentShift truncation notice if present |
| `foundationModel` | `metadata.platform_extensions.bedrock.foundation_model` | Preserve |
| `agentId` | `metadata.platform_extensions.bedrock.agent_id` | Preserve for round-trip |
| `agentResourceRoleArn` | `metadata.platform_extensions.bedrock.agent_role_arn` | Preserve |
| `idleSessionTTLInSeconds` | `metadata.platform_extensions.bedrock.idle_session_ttl` | Preserve |
| `createdAt` | `metadata.created_at` | ISO 8601 format |
| `updatedAt` | `metadata.updated_at` | ISO 8601 format |

### 3.2 Platform metadata

```python
ir.metadata.source_platform = "bedrock"
ir.metadata.platform_extensions["bedrock"] = {
    "agent_id": agent_id,
    "foundation_model": foundation_model,
    "agent_role_arn": agent_role_arn,
    "idle_session_ttl": idle_session_ttl,
    # Preserve alias info if available:
    "alias_id": alias_id,
    "alias_name": alias_name,
}
```

### 3.3 Instruction parsing → `persona.system_prompt` + `persona.sections`

1. **Truncation notice removal:** If `instruction` contains the AgentShift truncation notice
   `[AGENTSHIFT: Full instructions truncated...]`, strip the notice. If `instruction-full.txt`
   exists, use its content instead.

2. **Section extraction:** Run the section extractor (`extract_sections()`) on the instruction
   text. If the instruction was assembled by the AgentShift emitter, it will contain `## Heading`
   markdown structure that can be reconstructed. Populate `persona.sections` if headings are found.

3. **Language detection:** If the instruction contains a language directive (e.g., "Respond in
   Spanish"), set `persona.language` accordingly. Default to `"en"`.

### 3.4 Action groups → `ir.tools`

For each action group in the agent:

1. **If `openapi.json` is present:** Parse each path's `operationId`, `description`, and request
   body schema to reconstruct a `Tool`:
   ```python
   Tool(
       name=operationId,
       description=operation["description"],
       kind="openapi",          # or "shell" if x-agentshift-stub is set
       parameters=request_body_schema,
       endpoint=None,           # Bedrock doesn't expose real endpoints
   )
   ```

2. **If `openapi.json` is absent:** Create one stub tool per action group:
   ```python
   Tool(
       name=action_group["actionGroupName"],
       description=action_group.get("description", ""),
       kind="unknown",
   )
   ```

3. **Lambda ARN handling:** The Lambda ARN in `actionGroupExecutor.lambda` is preserved in
   `tool.endpoint` as an `arn:` URI. The dev who deploys sets this up separately.

4. **`x-agentshift-stub` detection:** If an OpenAPI operation has `"x-agentshift-stub": true`,
   the tool `kind` should be set to `"shell"` or `"mcp"` based on the path pattern:
   - Path ends in `/run` → `kind="shell"`
   - Path ends in `/action` → `kind="mcp"`

**Tool auth reconstruction:** If the action group's Lambda ARN matches the environment variable
pattern (from emitter TODO comments), emit a `ToolAuth` with `type="api_key"` and the inferred
`env_var` name.

### 3.5 Knowledge bases → `ir.knowledge`

For each knowledge base entry:
```python
KnowledgeSource(
    name=knowledge_base["knowledgeBaseId"],   # Use ID as name (real name not in this response)
    kind="vector_store",
    description=knowledge_base.get("description", ""),
    load_mode="indexed",
)
```

The `knowledge_base["description"]` field is used as the knowledge source name if meaningful;
otherwise the `knowledgeBaseId` is used as a fallback.

### 3.6 Guardrail config → `ir.governance`

**From `guardrail-config.json` (AgentShift-generated):**

Parse `topicPolicyConfig.topicsConfig` as `PlatformAnnotation` entries:
```python
PlatformAnnotation(
    id=f"PA-{i+1:03d}",
    kind="denied_topics",
    description=topic["definition"],
    platform_target="bedrock",
    config={"topicPolicyConfig": {"topicsConfig": [topic]}},
)
```

**From `guardrailConfiguration` in `bedrock-agent.json`:**

When the agent references a guardrail by ID, add a minimal annotation:
```python
PlatformAnnotation(
    id=f"PA-guardrail-{guardrail_id}",
    kind="content_filter",
    description=f"Bedrock Guardrail {guardrail_id} (v{guardrail_version})",
    platform_target="bedrock",
    config={
        "guardrailId": guardrail_id,
        "guardrailVersion": guardrail_version,
    },
)
```

**Guardrail text → L1 guardrails:** The parser SHOULD scan `persona.system_prompt` for common
guardrail patterns and extract them as `Guardrail` objects (see §4 for the heuristic).

---

## 4. System Prompt → L1 Guardrail Heuristic

When the instruction text contains guardrail-like sentences, extract them as `Guardrail` objects
so that `governance.guardrails` is populated even when there is no explicit L1 governance data.

**Trigger patterns (case-insensitive):**
- `"never "` at word boundary
- `"do not "` at word boundary
- `"always "` at word boundary (advisory-positive guardrails)
- `"must not "` at word boundary
- `"avoid "` at word boundary
- `"prohibited"`, `"forbidden"`, `"not allowed"`

**Algorithm:**
1. Split `system_prompt` into sentences (split on `.`, `!`, `?`, and newlines).
2. For each sentence, check if it matches any trigger pattern.
3. If matched, create a `Guardrail` with:
   - `id`: `"G{n:03d}"` (auto-incremented)
   - `text`: the matched sentence (stripped)
   - `category`: inferred from keywords (see table below)
   - `severity`: `"medium"` (default)

**Category inference:**

| Keyword in sentence | Inferred category |
|--------------------|-------------------|
| `diagnos`, `medic`, `prescri`, `treatment` | `safety` |
| `PII`, `personal`, `identif`, `private`, `confidential` | `privacy` |
| `GDPR`, `HIPAA`, `COPPA`, `regulatory`, `legal`, `comply` | `compliance` |
| `bias`, `discriminat`, `fair`, `honest` | `ethical` |
| `topic`, `subject`, `discuss`, `respond only` | `scope` |
| (default) | `general` |

**Severity inference:**
- Sentence contains `"critical"`, `"never"`, `"must not"` → `critical`
- Sentence contains `"always"`, `"prohibited"` → `high`
- Default → `medium`

This heuristic is best-effort. It SHOULD be documented in the parser output (e.g., via a
`metadata.platform_extensions._ir.guardrail_extraction = "heuristic"` flag).

---

## 5. CloudFormation Parsing

When the primary input is `cloudformation.yaml` (AgentShift-generated or custom):

### 5.1 Resource extraction

1. Find the `AWS::Bedrock::Agent` resource (any logical ID).
2. Extract `Properties.Instruction`, `Properties.Description`, `Properties.FoundationModel`,
   `Properties.AgentName`, `Properties.ActionGroups`, `Properties.KnowledgeBases`.
3. If `Instruction` uses `!Sub` or YAML multiline scalars, resolve to a plain string.
4. Remove CloudFormation-specific YAML intrinsics (`!Ref`, `!GetAtt`, `!Sub`) — replace with
   placeholder strings flagged as `TODO`.

### 5.2 Parameter defaults

If `Properties` reference CloudFormation `!Ref` parameters, use the parameter `Default` value
as the resolved value. If no default exists, use a placeholder.

### 5.3 Action group Lambda ARN

The Lambda ARN in `ActionGroupExecutor.Lambda` often contains a `!Ref` or a TODO placeholder.
The parser should treat these as `endpoint: "TODO"` in the resulting `Tool`.

---

## 6. Parser Input Resolution Order

When multiple input files are present, apply this precedence:

1. If `instruction.txt` exists → use as `persona.system_prompt` (may be untruncated)
2. Else if `bedrock-agent.json` exists → use `instruction` field (strip truncation notice)
3. Else if `cloudformation.yaml` exists → extract `Instruction` from `AWS::Bedrock::Agent`

Tool extraction:
1. If `openapi.json` exists → parse operations as tools
2. Else extract from `ActionGroups[].actionGroupName` as stub tools

Governance extraction:
1. If `guardrail-config.json` exists → parse as `platform_annotations`
2. Else check `guardrailConfiguration` in `bedrock-agent.json` → create minimal annotation
3. Always run the L1 guardrail heuristic on `persona.system_prompt`

---

## 7. Parser Entry Point

The parser is implemented in `src/agentshift/parsers/bedrock.py`.

```python
def parse(input_dir: Path) -> AgentIR:
    """Parse Bedrock agent artifacts from a directory into an AgentIR.
    
    Reads any combination of:
    - bedrock-agent.json
    - cloudformation.yaml
    - instruction.txt
    - openapi.json
    - guardrail-config.json
    
    At least one of bedrock-agent.json or cloudformation.yaml must be present.
    """
```

**Alternative entry points for specific use cases:**

```python
def parse_api_response(agent_data: dict) -> AgentIR:
    """Parse a raw Bedrock GetAgent API response dict."""

def parse_cloudformation(cfn_yaml: str, openapi_json: str | None = None) -> AgentIR:
    """Parse from CloudFormation YAML string (+ optional OpenAPI JSON string)."""
```

---

## 8. CLI Integration

```bash
# Convert from Bedrock artifacts directory
agentshift convert ./bedrock-output/ --from bedrock --to openclaw

# Convert from a single bedrock-agent.json export
agentshift convert ./bedrock-agent.json --from bedrock --to openclaw

# Convert with explicit instruction file
agentshift convert ./bedrock-output/ --from bedrock --instruction instruction-full.txt --to ir

# Diff two agents (one from Bedrock, one from OpenClaw)
agentshift diff ./bedrock-output/ --from bedrock ./my-skill/ --from openclaw
```

---

## 9. Validation Notes

The parser output MUST pass `agentshift validate`. Key validation checks:

1. `ir.name` is non-empty.
2. `ir.persona.system_prompt` is non-empty.
3. All `tool.name` values are unique within the IR.
4. `governance.guardrails[].id` values are unique.
5. `governance.platform_annotations[].id` values are unique.

---

## 10. Round-Trip Fidelity

A round-trip is: `openclaw → bedrock → openclaw`.

**Guaranteed to survive:**
- Agent `name` and `description`
- `persona.system_prompt` (modulo Bedrock's 4,000-char truncation)
- `persona.sections` (if instruction contains `## Heading` markdown)
- Tool names and descriptions (from OpenAPI)
- Knowledge base descriptions

**Known lossy fields:**
- `persona.language` — embedded in instruction text but not a structured field
- `tool.auth` — partially inferred from Lambda ARN patterns
- `triggers` — not preserved in Bedrock artifacts (no trigger → CloudFormation mapping is not reversible)
- `install` — not applicable to Bedrock
- `constraints.required_bins` — Bedrock has no bin requirements

**Truncation recovery:** If `instruction-full.txt` is present alongside a truncated
`instruction.txt`, the parser MUST use `instruction-full.txt` as `system_prompt`.

---

## 11. Example Round-Trip

### Input (`bedrock-agent.json`):
```json
{
  "agentName": "weather",
  "description": "Get current weather and forecasts via wttr.in",
  "instruction": "## Overview\nI provide current weather and forecasts...\n\n## Behavior\n- Always state the location you're reporting for.\n- Use °C by default; offer °F on request.\n\n## Guardrails\nDo not provide weather advisories as official warnings.",
  "foundationModel": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "idleSessionTTLInSeconds": 1800
}
```

### Output IR:
```json
{
  "ir_version": "1.0",
  "name": "weather",
  "description": "Get current weather and forecasts via wttr.in",
  "persona": {
    "system_prompt": "## Overview\nI provide current weather and forecasts...\n\n## Behavior\n- Always state the location you're reporting for.\n- Use °C by default; offer °F on request.\n\n## Guardrails\nDo not provide weather advisories as official warnings.",
    "sections": {
      "overview": "I provide current weather and forecasts...",
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
    "source_platform": "bedrock",
    "platform_extensions": {
      "bedrock": {
        "foundation_model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "idle_session_ttl": 1800
      }
    }
  }
}
```

---

## Appendix A — AgentShift Truncation Notice Pattern

When detecting and stripping truncation notices from Bedrock instructions:

```python
import re

TRUNCATION_NOTICE_PATTERN = re.compile(
    r'\s*\[AGENTSHIFT: Full instructions truncated[^\]]*\]',
    re.IGNORECASE
)

def strip_truncation_notice(text: str) -> str:
    return TRUNCATION_NOTICE_PATTERN.sub("", text).strip()
```

---

## Appendix B — Common Bedrock API Shapes

### `ListAgents` response item:
```json
{
  "agentId": "ABCD1234",
  "agentName": "my-agent",
  "agentStatus": "PREPARED",
  "description": "Agent description",
  "updatedAt": "2024-01-20T14:22:00Z"
}
```

Note: `instruction` and `actionGroups` are only available in `GetAgent` (not `ListAgents`).

### `GetAgent` response (complete):
```json
{
  "agent": {
    "agentId": "ABCD1234",
    "agentArn": "arn:aws:bedrock:us-east-1::agent/ABCD1234",
    "agentName": "my-agent",
    "agentStatus": "PREPARED",
    "agentResourceRoleArn": "arn:aws:iam::123:role/BedrockAgentRole",
    "createdAt": "2024-01-15T10:30:00Z",
    "description": "Agent description",
    "foundationModel": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "idleSessionTTLInSeconds": 1800,
    "instruction": "You are...",
    "preparedAt": "2024-01-15T10:35:00Z",
    "updatedAt": "2024-01-20T14:22:00Z",
    "promptOverrideConfiguration": {}
  }
}
```

Action groups and knowledge bases are fetched separately via:
- `ListAgentActionGroups` → `/agents/{agentId}/agentversions/{agentVersion}/actiongroups/`
- `ListAgentKnowledgeBases` → `/agents/{agentId}/agentversions/{agentVersion}/knowledgebases/`
