# Governance IR Schema — L1/L2/L3 Layers, GPR/CFS Scoring, Elevation Rules

**Spec ID:** A12
**Status:** Canonical
**Author:** @architect
**IR Version:** v0.3 (additive to v1.0)
**Closes:** A12 (Week 7 backlog)

---

## 1. Overview

AgentShift's governance framework provides a **three-layer model** for expressing agent safety
and permission constraints in the Intermediate Representation (IR). This allows governance
metadata to survive round-trips across platforms — even when a target platform cannot express
the constraint natively (it is "elevated" to a prompt-level instruction instead).

The framework also provides a **scoring system** (GPR and CFS) used by `agentshift audit` to
measure how faithfully governance constraints are preserved when an agent is converted to a
target platform. This spec documents the schema already implemented in `src/agentshift/ir.py`,
`src/agentshift/governance_audit.py`, and `src/agentshift/elevation.py`.

```
┌─────────────────────────────────────────────────────────────────┐
│  governance                                                       │
│    L1 ── guardrails[]          (prompt-level rules)             │
│    L2 ── tool_permissions[]    (tool-level access controls)     │
│    L3 ── platform_annotations[] (platform-native controls)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Governance Layer Definitions

### 2.1 Layer 1 — Prompt-Level Guardrails (L1)

**What they are:** Rules that are embedded directly in the agent's system prompt. They are
expressed as natural language instructions (e.g., "Never provide medical diagnoses").
L1 guardrails are platform-universal — every agent platform can express them as prompt text.

**Preservation guarantee:** L1 guardrails are **always preserved** during conversion. They
appear in the `instruction` / `goal` / `system_prompt` field of every target platform's output.

**Python model (`ir.py`):**
```python
class Guardrail(BaseModel):
    id: str                   # Unique identifier, e.g. "G001"
    text: str                 # The guardrail rule as natural language
    category: Literal[
        "safety", "privacy", "compliance",
        "ethical", "operational", "scope", "general"
    ] = "general"
    severity: Literal["critical", "high", "medium", "low"] = "medium"
```

**JSON representation:**
```json
{
  "governance": {
    "guardrails": [
      {
        "id": "G001",
        "text": "Never provide medical diagnoses or treatment recommendations.",
        "category": "safety",
        "severity": "critical"
      },
      {
        "id": "G002",
        "text": "Do not share personally identifiable information about users.",
        "category": "privacy",
        "severity": "high"
      }
    ]
  }
}
```

**Category definitions:**

| Category | Description |
|----------|-------------|
| `safety` | Rules preventing harmful outputs (violence, self-harm, medical misinformation) |
| `privacy` | Rules protecting user data and PII |
| `compliance` | Regulatory or legal requirements (GDPR, HIPAA, COPPA) |
| `ethical` | Bias prevention, fairness, honesty requirements |
| `operational` | Scope limits, response format, availability constraints |
| `scope` | Topic restrictions — what the agent will/won't discuss |
| `general` | Default catch-all for uncategorized rules |

**Severity levels:**

| Level | Meaning |
|-------|---------|
| `critical` | Must be preserved at all costs; flag if dropped |
| `high` | Strong requirement; warn if degraded |
| `medium` | Standard rule; note if not fully expressed |
| `low` | Advisory; preserve when possible |

---

### 2.2 Layer 2 — Tool-Level Permission Controls (L2)

**What they are:** Fine-grained access controls for individual tools. These go beyond "tool
enabled/disabled" — they express patterns, scopes, rate limits, and access modes. L2 controls
have **partial native support** across platforms (e.g., Bedrock supports disabled tools but not
deny patterns; Claude Code supports allow/deny lists).

**When native support is absent**, L2 controls are **elevated** to L1 prompt instructions by the
elevation engine.

**Python model (`ir.py`):**
```python
class ToolPermission(BaseModel):
    tool_name: str                  # Matches a tool name in ir.tools[]
    enabled: bool = True            # False = tool is disabled
    access: Literal[
        "full", "read-only", "disabled"
    ] = "full"
    deny_patterns: list[str] = []   # Glob/regex patterns of disallowed inputs
    allow_patterns: list[str] = []  # Glob/regex patterns of allowed inputs (allowlist)
    rate_limit: str | None = None   # e.g. "10/minute", "100/day"
    max_value: str | None = None    # e.g. "$50", "1000 tokens"
    notes: str | None = None        # Human-readable notes
```

**JSON representation:**
```json
{
  "governance": {
    "tool_permissions": [
      {
        "tool_name": "filesystem",
        "enabled": true,
        "access": "read-only",
        "deny_patterns": ["**/.env", "**/secrets/**"],
        "allow_patterns": ["/home/user/docs/**"],
        "notes": "Read-only access to user documents only"
      },
      {
        "tool_name": "web_search",
        "enabled": true,
        "access": "full",
        "rate_limit": "20/hour",
        "notes": "Rate-limited to prevent abuse"
      },
      {
        "tool_name": "dangerous_tool",
        "enabled": false,
        "access": "disabled",
        "notes": "Disabled in this deployment environment"
      }
    ]
  }
}
```

**L2 permission types and platform support:**

| Permission type | Claude Code | Bedrock | Vertex AI | Copilot | LangGraph |
|-----------------|-------------|---------|-----------|---------|-----------|
| `enabled: false` (disabled tool) | ✅ native | ✅ native | ✅ native | ❌ → L1 | ✅ native |
| `access: read-only` | ✅ native | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
| `deny_patterns` | ✅ native | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
| `allow_patterns` | ✅ native | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
| `rate_limit` | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
| `max_value` | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |

**Key insight:** Rate limits and max value constraints have no native support on any current
platform — they are always elevated to L1 instructions.

---

### 2.3 Layer 3 — Platform-Native Governance Annotations (L3)

**What they are:** Controls that exist as first-class features on specific platforms but have no
general equivalent. L3 annotations are expressed in the IR for round-trip fidelity and to allow
cross-platform elevation when migrating agents.

**Python model (`ir.py`):**
```python
class PlatformAnnotation(BaseModel):
    id: str                           # Unique identifier, e.g. "PA001"
    kind: Literal[
        "content_filter",
        "pii_detection",
        "denied_topics",
        "grounding_check"
    ] = "content_filter"
    description: str                  # Human-readable description
    platform_target: Literal[
        "bedrock", "vertex-ai", "m365", "any"
    ] = "any"
    config: dict[str, Any] = {}       # Platform-specific configuration blob
```

**JSON representation:**
```json
{
  "governance": {
    "platform_annotations": [
      {
        "id": "PA001",
        "kind": "content_filter",
        "description": "Block hate speech and violent content",
        "platform_target": "bedrock",
        "config": {
          "contentPolicyConfig": {
            "filtersConfig": [
              { "type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH" },
              { "type": "VIOLENCE", "inputStrength": "HIGH", "outputStrength": "HIGH" }
            ]
          }
        }
      },
      {
        "id": "PA002",
        "kind": "pii_detection",
        "description": "Mask names, emails, and phone numbers in outputs",
        "platform_target": "vertex-ai",
        "config": {
          "sensitiveDataProtectionConfig": {
            "inspectConfig": {
              "infoTypes": ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON_NAME"]
            }
          }
        }
      },
      {
        "id": "PA003",
        "kind": "denied_topics",
        "description": "Deny discussion of competitor products",
        "platform_target": "bedrock",
        "config": {
          "topicPolicyConfig": {
            "topicsConfig": [
              {
                "name": "competitor-products",
                "definition": "Discussion or comparison of products from competing services",
                "type": "DENY"
              }
            ]
          }
        }
      }
    ]
  }
}
```

**L3 annotation kinds:**

| Kind | Bedrock native | Vertex AI native | Elevation target |
|------|---------------|------------------|-----------------|
| `content_filter` | ✅ (`AWS::Bedrock::Guardrail`) | ✅ (Safety attributes) | L1 instruction |
| `pii_detection` | ✅ (`sensitiveInformationPolicyConfig`) | ✅ (DLP integration) | L1 instruction |
| `denied_topics` | ✅ (`topicPolicyConfig`) | ❌ | L1 instruction |
| `grounding_check` | ✅ (`groundingPolicyConfig`) | ❌ | L1 instruction |

**L3 elevation instructions (when native support is absent):**

| Kind | Elevated L1 instruction template |
|------|----------------------------------|
| `content_filter` | `CONTENT POLICY: {description}` |
| `pii_detection` | `PII PROTECTION: {description}` |
| `denied_topics` | `DENIED TOPIC: {description}` |
| `grounding_check` | `GROUNDING REQUIREMENT: {description}` |

---

## 3. Governance Container — Full Schema

```python
class Governance(BaseModel):
    guardrails: list[Guardrail] = []
    tool_permissions: list[ToolPermission] = []
    platform_annotations: list[PlatformAnnotation] = []
```

**Placement in AgentIR:**
```python
class AgentIR(BaseModel):
    ...
    governance: Governance = Field(default_factory=Governance)
    ...
```

**Complete IR example with all three layers:**
```json
{
  "ir_version": "1.0",
  "name": "medical-assistant",
  "description": "Clinical information assistant for healthcare professionals",
  "governance": {
    "guardrails": [
      {
        "id": "G001",
        "text": "Never provide diagnoses — direct users to qualified healthcare providers.",
        "category": "safety",
        "severity": "critical"
      },
      {
        "id": "G002",
        "text": "Do not share patient-identifying information under any circumstances.",
        "category": "privacy",
        "severity": "critical"
      }
    ],
    "tool_permissions": [
      {
        "tool_name": "drug_database",
        "enabled": true,
        "access": "read-only",
        "rate_limit": "50/minute",
        "notes": "Read-only access; rate-limited for compliance"
      },
      {
        "tool_name": "patient_records",
        "enabled": false,
        "access": "disabled",
        "notes": "Disabled — requires HIPAA BAA before enabling"
      }
    ],
    "platform_annotations": [
      {
        "id": "PA001",
        "kind": "pii_detection",
        "description": "Detect and mask PHI in all outputs",
        "platform_target": "bedrock",
        "config": {}
      }
    ]
  }
}
```

---

## 4. Elevation Engine

### 4.1 Purpose

The elevation engine (`src/agentshift/elevation.py`) transforms L2/L3 governance artifacts into
L1 prompt instructions for platforms that lack native support. It produces an `ElevationResult`
that:

1. Classifies each governance artifact as `preserved`, `elevated`, or `dropped`.
2. Generates natural language instructions for elevated artifacts.
3. Provides a full audit trail for governance reporting.

### 4.2 Platform Capability Matrix

```python
PLATFORM_L2_CAPABILITIES = {
    "claude-code": {"allow_list", "deny_list", "deny_patterns", "disabled_tool"},
    "copilot":     set(),           # No native permission model
    "bedrock":     {"disabled_tool"},
    "vertex":      {"disabled_tool"},
    "m365":        set(),
    "langgraph":   {"disabled_tool"},
}

PLATFORM_L3_CAPABILITIES = {
    "claude-code": set(),           # No native content filters
    "copilot":     set(),
    "bedrock":     {"content_filter", "pii_detection", "denied_topics", "grounding_check"},
    "vertex":      {"content_filter", "pii_detection"},
    "m365":        set(),
    "langgraph":   set(),
}
```

### 4.3 Elevation Decision Logic

For each L2 `ToolPermission`:

1. **Disabled tool** (`enabled: false`) — Check if `"disabled_tool"` is in platform capabilities.
   - If yes → `l2_preserved`
   - If no → generate instruction `"Do NOT use the {tool_name} tool. It is disabled."` → `l2_elevated`

2. **Deny patterns** — Check if `"deny_patterns"` is in platform capabilities.
   - If yes → `l2_preserved`
   - If no → generate per-pattern instructions → `l2_elevated`

3. **Read-only access** — Check if `"deny_list"` is in platform capabilities.
   - If yes → `l2_preserved`
   - If no → generate instruction → `l2_elevated`

4. **Rate limits** — Always elevated (no platform supports native rate limiting).
   - Generate instruction `"Rate limit for {tool_name}: do not exceed {rate_limit}."` → `l2_elevated`

5. **Max value** — Always elevated (no platform supports native max-value constraints).
   - Generate instruction → `l2_elevated`

6. **Allow patterns** — Check if `"allow_list"` is in platform capabilities.
   - If yes → `l2_preserved`
   - If no → generate per-pattern instructions → `l2_elevated`

A `ToolPermission` is classified `l2_elevated` if **any** of its sub-controls were elevated.

For each L3 `PlatformAnnotation`:
- Check if `ann.kind` is in `PLATFORM_L3_CAPABILITIES[target]`.
  - If yes → `l3_preserved`
  - If can generate instruction → `l3_elevated`
  - If not expressible as L1 instruction → `l3_dropped`

### 4.4 ElevationResult Schema

```python
@dataclass
class ElevatedArtifact:
    source_layer: str         # "L2" or "L3"
    artifact_id: str          # e.g. "L2-filesystem-readonly"
    artifact_type: str        # "deny_pattern", "rate_limit", "disabled_tool", etc.
    original_text: str        # Original constraint expression
    elevated_instruction: str # Generated L1 instruction text
    target_platform: str      # Platform this elevation is for
    reason: str               # Why elevation was needed

@dataclass
class ElevationResult:
    target: str
    elevated_artifacts: list[ElevatedArtifact]
    l1_preserved: list[Guardrail]
    l2_preserved: list[ToolPermission]
    l2_elevated: list[ToolPermission]
    l3_preserved: list[PlatformAnnotation]
    l3_elevated: list[PlatformAnnotation]
    l3_dropped: list[PlatformAnnotation]
    extra_instructions: list[str]  # Generated L1 text to prepend to system prompt
```

---

## 5. GPR — Governance Preservation Rate

GPR measures what fraction of governance artifacts survive conversion to a target platform with
**native enforcement** (not elevated to prompt text, which the model may ignore).

### 5.1 GPR-L1 (Prompt-Level Preservation)

All L1 guardrails are expressed as prompt text on every platform — they are always "preserved"
in the sense that they appear in the output. GPR-L1 = 1.0 by design unless the instruction is
truncated.

```
GPR-L1 = len(l1_preserved) / len(gov.guardrails)
```

When `l1_total == 0`, GPR-L1 = 1.0 (vacuously true — no guardrails to lose).

**Important:** The truncation scenario (prompt exceeds platform limit) can cause L1 guardrails
to be dropped. In that case, `l1_preserved` should only count guardrails that fit within the
truncated instruction. This is not yet implemented but is flagged as a future enhancement.

### 5.2 GPR-L2 (Tool Permission Preservation)

GPR-L2 measures native enforcement of tool-level permissions. **Elevated artifacts are NOT
counted as preserved** — they lose their enforcement layer (a prompt instruction is advisory,
not enforced).

```
GPR-L2 = len(l2_preserved) / len(gov.tool_permissions)
```

- `l2_preserved`: ToolPermissions where all sub-controls are natively supported.
- `l2_elevated`: ToolPermissions where at least one sub-control was elevated to L1.

When `l2_total == 0`, GPR-L2 = 1.0.

### 5.3 GPR-L3 (Platform Annotation Preservation)

GPR-L3 measures native enforcement of platform-native governance controls.

```
GPR-L3 = len(l3_preserved) / len(gov.platform_annotations)
```

- `l3_preserved`: Annotations supported natively on the target.
- `l3_elevated`: Annotations not natively supported but expressible as L1 instructions.
- `l3_dropped`: Annotations that cannot be expressed at all on the target.

When `l3_total == 0`, GPR-L3 = 0.0 (not vacuously 1.0 — this signals that L3 governance
was not specified, which is a design choice worth surfacing in reports).

### 5.4 GPR-Overall (Weighted Aggregate)

```
GPR-Overall = (l1_preserved + l2_preserved + l3_preserved) /
              (l1_total + l2_total + l3_total)
```

When all totals are zero, GPR-Overall = 1.0 (agent has no governance; fully portable).

**Interpretation guide:**

| GPR-Overall | Meaning |
|-------------|---------|
| 1.0 | All governance enforced natively on target |
| 0.9–0.99 | Near-perfect; minor controls elevated to prompt |
| 0.5–0.89 | Significant governance degradation; review elevated artifacts |
| < 0.5 | Majority of governance is advisory-only on this target |

---

## 6. CFS — Conversion Fidelity Score

CFS measures how faithfully the **non-governance** parts of the agent survive conversion.
It complements GPR, which focuses on governance only.

### 6.1 CFS Component Checks

CFS is computed as the mean of four boolean checks:

| Check | Field | Pass condition |
|-------|-------|---------------|
| `cfs_identity` | `ir.name`, `ir.description` | Both are non-empty strings |
| `cfs_tools_listed` | `ir.tools` | List is accessible (always true; tools may be empty) |
| `cfs_memory_handled` | N/A | Always `True` — memory is intentionally not converted (documented behavior) |
| `cfs_schema_valid` | N/A | `True` by assumption (use `agentshift validate` to check) |

```
CFS = (cfs_identity + cfs_tools_listed + cfs_memory_handled + cfs_schema_valid) / 4
```

**Note:** CFS is intentionally simple in v0.3. Future versions may add:
- `cfs_tools_coverage`: fraction of tools that have native equivalents
- `cfs_knowledge_coverage`: fraction of knowledge sources that survive
- `cfs_triggers_coverage`: fraction of triggers that survive

### 6.2 CFS vs GPR

| Score | Focus | Range | "Perfect" value |
|-------|-------|-------|----------------|
| GPR-L1 | Prompt guardrails preserved natively | [0, 1] | 1.0 |
| GPR-L2 | Tool permissions preserved natively | [0, 1] | 1.0 |
| GPR-L3 | Platform annotations preserved natively | [0, 1] | 1.0 |
| GPR-Overall | Weighted governance preservation | [0, 1] | 1.0 |
| CFS | Non-governance fidelity | [0, 1] | 1.0 |

---

## 7. Audit Report

The `GovernanceAudit` dataclass records full metrics for a single agent × target conversion.

```python
@dataclass
class GovernanceAudit:
    agent_id: str
    agent_name: str
    target: str
    domain: str                     # e.g. "healthcare", "finance"
    complexity: str                 # e.g. "simple", "moderate", "complex"

    # L1
    l1_total: int
    l1_preserved: int
    gpr_l1: float

    # L2
    l2_total: int
    l2_preserved: int
    l2_elevated: int
    gpr_l2: float

    # L3
    l3_total: int
    l3_preserved: int
    l3_elevated: int
    l3_dropped: int
    gpr_l3: float

    # Overall
    gpr_overall: float

    # CFS components
    cfs_identity: bool
    cfs_tools_listed: bool
    cfs_memory_handled: bool
    cfs_schema_valid: bool
    cfs: float

    # Elevation audit trail
    elevated_artifacts: list[dict]
```

**Export formats:** CSV (tabular, for paper Tables IV/VII/VIII) and JSON (full detail including
`elevated_artifacts`).

---

## 8. CLI Integration

The governance audit is exposed via `agentshift audit`:

```bash
# Audit a single agent against all default targets
agentshift audit agent.json

# Audit with custom targets
agentshift audit agent.json --targets bedrock,vertex,copilot

# Export results
agentshift audit agent.json --export-csv audit.csv --export-json audit.json

# Show elevation analysis table
agentshift audit agent.json --show-elevations

# Batch audit multiple agents
agentshift audit agents/*.json --targets bedrock
```

The `agentshift convert` command automatically runs a governance audit when converting and
displays a summary if any L2/L3 controls were elevated or dropped.

---

## 9. IR Placement and Backward Compatibility

### 9.1 Position in AgentIR

`governance` is a top-level field in `AgentIR` with a default empty `Governance()` value.
Existing IRs without a `governance` field remain fully valid — the field defaults to no
guardrails, no tool permissions, no platform annotations.

### 9.2 No Version Bump Required

Adding governance fields to an existing IR does not change `ir_version`. Consumers that do not
understand the `governance` field ignore it. The schema uses `extra: "forbid"` to ensure invalid
fields are caught, but `governance` was already added to `AgentIR` in the implementation.

### 9.3 Parsers Populating Governance

Parsers that extract governance from source formats SHOULD:
1. Parse explicit guardrail language from the system prompt (e.g., "Never", "Do not", "Always").
2. Map platform-specific guardrail configs to `platform_annotations` with the appropriate `platform_target`.
3. Map tool permission configs (e.g., Claude Code `settings.json` permissions) to `tool_permissions`.

Parsers MAY leave `governance` empty when governance extraction is not feasible.

---

## 10. Research Paper Context

This governance framework was designed to support a research paper comparing governance
preservation across agent conversion targets. The key tables produced by the audit engine are:

| Table | Content | Produced by |
|-------|---------|-------------|
| Table IV | GPR by target platform (aggregate) | `render_summary_by_target()` |
| Table VII | Per-agent breakdown (GPR-CC vs GPR-CP Δ) | `render_per_agent_breakdown()` |
| Table VIII | Elevation analysis by artifact type and target | `render_elevation_analysis()` |

**Hypothesis:** Claude Code (CC) achieves higher GPR than Copilot (CP) because CC natively
supports allow/deny lists and deny patterns, while Copilot has no native permission model.

---

## 11. Files in This System

| File | Role |
|------|------|
| `src/agentshift/ir.py` | `Guardrail`, `ToolPermission`, `PlatformAnnotation`, `Governance` models |
| `src/agentshift/elevation.py` | `elevate_governance()`, platform capability matrices, `ElevationResult` |
| `src/agentshift/governance_audit.py` | `audit_conversion()`, `GovernanceAudit`, GPR/CFS computation, export |
| `specs/governance-ir-schema.md` | This document — authoritative spec |

---

## Appendix A — Elevation Instruction Templates

When a governance artifact is elevated to L1, the following instruction templates are used:

| Artifact type | Template |
|---------------|---------|
| `disabled_tool` | `"Do NOT use the {tool_name} tool. It is disabled."` |
| `deny_pattern` | `"When using {tool_name}, NEVER access paths matching: {pattern}"` |
| `access_restriction` (read-only) | `"The {tool_name} tool is READ-ONLY. Do NOT use it to write, modify, or delete any data."` |
| `rate_limit` | `"Rate limit for {tool_name}: do not exceed {rate_limit}."` |
| `max_value` | `"Maximum value constraint for {tool_name}: {max_value}."` |
| `allow_pattern` | `"The {tool_name} tool may ONLY be used for paths matching: {pattern}"` |
| `content_filter` | `"CONTENT POLICY: {description}"` |
| `pii_detection` | `"PII PROTECTION: {description}"` |
| `denied_topics` | `"DENIED TOPIC: {description}"` |
| `grounding_check` | `"GROUNDING REQUIREMENT: {description}"` |

---

## Appendix B — Platform Capability Summary

| Platform | L1 support | L2: disabled tool | L2: deny patterns | L2: allow list | L3: content filter | L3: PII | L3: denied topics | L3: grounding |
|----------|------------|-------------------|-------------------|----------------|--------------------|---------|-------------------|---------------|
| **claude-code** | ✅ always | ✅ native | ✅ native | ✅ native | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
| **bedrock** | ✅ always | ✅ native | ❌ → L1 | ❌ → L1 | ✅ native | ✅ native | ✅ native | ✅ native |
| **vertex** | ✅ always | ✅ native | ❌ → L1 | ❌ → L1 | ✅ native | ✅ native | ❌ → L1 | ❌ → L1 |
| **copilot** | ✅ always | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
| **m365** | ✅ always | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
| **langgraph** | ✅ always | ✅ native | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 | ❌ → L1 |
