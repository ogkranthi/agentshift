# persona.sections Schema — IR v0.2

**Spec ID:** A11
**Status:** Draft
**Author:** @architect
**IR Version:** v0.2 (additive to v1.0)
**Closes:** GitHub issue #3

---

## 1. Overview

`persona.system_prompt` is currently a flat string — the entire SKILL.md body or CLAUDE.md content is placed into a single field. This works for basic round-trips, but loses structural information that platforms can use for smarter rendering, guardrails mapping, and diffing.

This spec introduces an optional `persona.sections` map: a structured decomposition of the system prompt into named semantic sections. The `system_prompt` field remains the canonical, authoritative instruction string. `sections` is purely additive — it provides structured access to the same content.

```
┌─────────────────────────────────────────────────────────┐
│ persona                                                   │
│   system_prompt: "# Overview\nYou are...\n## Behavior\n" │  ← canonical
│   sections:                                               │  ← optional map
│     overview:    "You are..."                             │
│     behavior:    "..."                                    │
│     guardrails:  "..."                                    │
│     tools:       "..."                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 2. JSON Schema Extension

### 2.1 Updated `persona` object in `ir-schema.json`

The following diff adds the `sections` property to the existing `persona` definition:

```json
"persona": {
  "type": "object",
  "description": "The agent's identity and behavioral instructions — the system prompt layer.",
  "additionalProperties": false,
  "properties": {
    "system_prompt": {
      "type": "string",
      "description": "The full system / instruction prompt passed to the model at session start. Canonical flattened form. Maps to: OpenClaw SKILL.md body, Claude Code CLAUDE.md, Copilot system_prompt, Bedrock instruction, Vertex AI agent instruction."
    },
    "personality_notes": {
      "type": "string",
      "description": "Human-readable prose describing tone, style, and personality. Informational only; may be embedded in system_prompt."
    },
    "language": {
      "type": "string",
      "description": "Primary language for responses. BCP-47 code. e.g. 'en', 'es'.",
      "default": "en"
    },
    "sections": {
      "type": "object",
      "description": "Optional structured decomposition of system_prompt into named semantic sections. Keys are section slugs (lowercase, hyphens). Values are the section body text (excluding the heading). sections is additive — system_prompt remains authoritative.",
      "additionalProperties": {
        "type": "string"
      },
      "propertyNames": {
        "pattern": "^[a-z][a-z0-9-]*$"
      },
      "examples": [
        {
          "overview": "You are a warm, knowledgeable pregnancy companion...",
          "behavior": "Always respond with empathy...",
          "guardrails": "Never provide medical diagnoses...",
          "tools": "Use the calendar tool to track appointments..."
        }
      ]
    }
  }
}
```

### 2.2 IR version bump

The `ir_version` field remains `"1.0"` for fully backward-compatible documents. When `sections` is populated, parsers SHOULD set a `metadata.platform_extensions` hint to signal v0.2 enrichment:

```json
{
  "ir_version": "1.0",
  "metadata": {
    "platform_extensions": {
      "_ir": { "sections_populated": true }
    }
  }
}
```

This keeps the schema non-breaking while allowing downstream consumers to detect richer IRs.

---

## 3. Section Extraction — Parser Behaviour

### 3.1 Algorithm

Parsers that handle markdown-based sources (OpenClaw SKILL.md, Claude Code CLAUDE.md) SHOULD extract sections when headings are present.

**Algorithm:**

1. Parse the `system_prompt` string as markdown.
2. Scan for level-2 (`##`) headings. If none are found, scan for level-3 (`###`) headings.
3. For each heading found:
   a. Normalize the heading text to a slug: lowercase, strip punctuation, replace whitespace with `-`.
   b. Map the slug to a well-known name if a canonical alias exists (see §4).
   c. Collect all content between this heading and the next same-or-higher-level heading as the section body.
   d. Strip leading/trailing whitespace from the body.
4. Store the result in `persona.sections`.
5. Do **not** modify `system_prompt` — it stays intact.

**Heading level selection rule:** Use H2 if any H2 headings exist in the body; otherwise fall back to H3. Mixed-level documents use the lowest (highest priority) level found.

### 3.2 Example

Given a SKILL.md body:

```markdown
You are a weather assistant.

## Overview
I provide current weather and forecasts using wttr.in.

## Behavior
- Always state the location you're reporting for.
- Use °C by default; offer °F on request.

## Guardrails
Do not provide weather advisories as official warnings.

## Tools
Use the `fetch_weather` tool for all data retrieval.
```

The parser produces:

```json
{
  "system_prompt": "You are a weather assistant.\n\n## Overview\nI provide current weather...",
  "sections": {
    "overview": "I provide current weather and forecasts using wttr.in.",
    "behavior": "- Always state the location you're reporting for.\n- Use °C by default; offer °F on request.",
    "guardrails": "Do not provide weather advisories as official warnings.",
    "tools": "Use the `fetch_weather` tool for all data retrieval."
  }
}
```

Note that any content **before** the first heading is preserved only in `system_prompt` (as a preamble). Parsers MAY store it under a synthetic `preamble` key, but MUST NOT require it.

### 3.3 Heading normalization rules

| Raw heading | Normalized slug |
|-------------|----------------|
| `## Overview` | `overview` |
| `## Behavior` | `behavior` |
| `## Guardrails & Safety` | `guardrails-safety` |
| `## Tools & Integrations` | `tools-integrations` |
| `## My Rules` | `my-rules` |
| `### Data Sources` | `data-sources` |

Normalization steps:
1. Strip the leading `#` characters and trim whitespace.
2. Lowercase the result.
3. Replace all runs of non-alphanumeric characters (except `-`) with a single `-`.
4. Trim leading/trailing `-` characters.

---

## 4. Well-Known Section Names

These are the canonical slug names with defined semantic meaning. Parsers SHOULD map aliases to these names. Emitters use these names to drive platform-specific output.

| Canonical slug | Aliases | Semantic meaning |
|----------------|---------|-----------------|
| `overview` | `about`, `description`, `intro`, `introduction` | High-level description of the agent's purpose and identity |
| `behavior` | `instructions`, `rules`, `guidelines`, `how-i-work`, `how-to-use` | Core operating instructions, response rules, formatting preferences |
| `guardrails` | `safety`, `restrictions`, `limits`, `do-not`, `constraints` | Safety boundaries, refusal rules, topics to avoid |
| `tools` | `capabilities`, `integrations`, `tool-use`, `available-tools` | Description of tools the agent can use and how |
| `knowledge` | `context`, `background`, `data`, `knowledge-base` | Domain knowledge, background context, grounding information |
| `persona` | `personality`, `tone`, `voice`, `character`, `style` | Tone, communication style, personality traits |
| `examples` | `sample-interactions`, `usage-examples`, `demos` | Example prompts and responses |
| `triggers` | `when-to-use`, `activation`, `use-cases` | Conditions or scenarios that should invoke this agent |
| `output-format` | `format`, `output`, `response-format` | How responses should be structured or formatted |
| `auth` | `authentication`, `credentials`, `setup` | Authentication requirements and setup instructions |

### 4.1 Alias resolution

When a parser encounters a heading that matches a known alias, it MUST store the content under the **canonical** slug — not the alias. For example, a heading `## Safety` maps to `guardrails`, not `safety`.

If the same canonical slug would be populated twice (two sections mapping to the same canonical name), the parser MUST append the bodies with a `\n\n` separator and emit a debug-level warning.

---

## 5. Platform-Specific Emitter Mappings

`sections` enables smarter emitters. When `persona.sections` is present, emitters SHOULD use the structured data rather than the flat `system_prompt` where it improves quality or compliance.

### 5.1 Amazon Bedrock

Bedrock agents have a strict **4,000 character limit** on the `instruction` field and support separate `guardrailConfiguration`.

| IR section | Bedrock mapping | Notes |
|------------|----------------|-------|
| `overview` + `behavior` + `tools` + `knowledge` | `instruction` field | Primary instruction block. Emitter assembles these sections in order. |
| `guardrails` | `guardrailConfiguration.contentPolicyConfig.filtersConfig` topic filters | Extract refusal topics as filter entries. Use `BLOCK` strength for explicit prohibitions. |
| `persona` | Append to `instruction` as a style note (prefix: "Tone and style:") | Bedrock has no separate persona field |
| `examples` | Omit from `instruction` unless budget allows | Examples are verbose; drop first when near limit |

**Guardrail extraction example:**

Given:
```
guardrails: "Never provide medical diagnoses. Do not prescribe medications. Avoid discussing competitor products."
```

The emitter generates:
```json
{
  "guardrailConfiguration": {
    "contentPolicyConfig": {
      "filtersConfig": [
        { "type": "MEDICAL_DIAGNOSES", "inputStrength": "HIGH", "outputStrength": "HIGH" },
        { "type": "PRESCRIPTIONS", "inputStrength": "HIGH", "outputStrength": "HIGH" }
      ]
    },
    "topicPolicyConfig": {
      "topicsConfig": [
        { "name": "competitor-products", "definition": "Discussion of competitor products", "type": "DENY" }
      ]
    }
  }
}
```

When `sections` is absent, the emitter falls back to using `system_prompt` for the `instruction` field and emits no guardrail config (existing behavior).

### 5.2 Google Vertex AI Agent Builder

Vertex AI agents use a single `goal` field (8,000 char limit) plus optional `instructions`.

| IR section | Vertex mapping | Notes |
|------------|---------------|-------|
| `overview` | `agent.goal` | Primary goal statement |
| `behavior` + `persona` + `tools` + `knowledge` | `agent.instructions` | Combined instruction block |
| `guardrails` | Appended to `agent.instructions` as "Restrictions:" prefix | Vertex has no separate guardrail field |
| `examples` | Omit (character budget) | |

When `sections` is absent, both `goal` and `instructions` are derived from `system_prompt` using the existing truncation strategy.

### 5.3 Microsoft Copilot (Declarative Agents)

Copilot declarative agents use `instructions` (up to 8,000 characters) in the manifest JSON.

| IR section | Copilot mapping | Notes |
|------------|----------------|-------|
| `overview` | Prepended to `instructions` as the opening paragraph | Provides clear agent identity |
| `behavior` + `tools` + `knowledge` | `instructions` body | Core instructions |
| `guardrails` | Appended to `instructions` as "Restrictions:" block | Copilot enforces these via content policy at runtime |
| `persona` | Appended as "Communication style:" block | |
| `examples` | Omit from `instructions`; MAY generate `conversation_starters` array | |

### 5.4 OpenClaw SKILL.md

OpenClaw uses the full SKILL.md markdown body. When `sections` is present, the emitter SHOULD reconstruct the body with proper H2 headings rather than dumping the flat `system_prompt`:

```markdown
## Overview
{sections.overview}

## Behavior
{sections.behavior}

## Guardrails
{sections.guardrails}

## Tools
{sections.tools}
```

Section order: `overview`, `behavior`, `guardrails`, `tools`, `knowledge`, `persona`, `examples`, then any custom sections alphabetically.

### 5.5 Claude Code (CLAUDE.md)

Claude Code uses `CLAUDE.md` free-form markdown. Same reconstruction approach as OpenClaw. The `guardrails` section maps to a `## Rules` heading in Claude Code convention.

---

## 6. `agentshift diff` — Per-Section Comparison

When both IRs being diffed have `persona.sections` populated, `agentshift diff` SHOULD perform a section-level comparison in addition to the existing component-level portability matrix.

### 6.1 Section diff modes

`agentshift diff` supports two invocation modes:

#### Mode A: Portability diff (existing)
```
agentshift diff agent.json --targets bedrock,vertex,copilot
```
Produces the existing portability matrix. If `sections` is present, adds a **"Persona Sections"** row showing which sections survive to each target.

#### Mode B: Agent-to-agent diff (new in v0.2)
```
agentshift diff agent-v1.json agent-v2.json
```
Produces a per-section diff between two IRs of the same agent.

### 6.2 Section-level portability row

When `sections` is populated and running Mode A, the portability matrix gains a new row:

```
┌─────────────────┬────────┬─────────────────┬──────────────────────┬──────────────────────┐
│ Component       │ Source │ bedrock         │ vertex               │ copilot              │
├─────────────────┼────────┼─────────────────┼──────────────────────┼──────────────────────┤
│ Instructions    │ ✅     │ ⚠️  truncated    │ ✅ 100%              │ ✅ 100%              │
│ Persona Sections│ ✅ 4   │ ⚠️  3/4 mapped  │ ⚠️  3/4 mapped       │ ✅ 4/4 mapped        │
└─────────────────┴────────┴─────────────────┴──────────────────────┴──────────────────────┘
```

The "Persona Sections" row shows `N/M mapped` where N is the number of sections that have a direct platform mapping and M is the total sections present. The `guardrails` section on Bedrock counts as "mapped" because it routes to `guardrailConfiguration`.

### 6.3 Agent-to-agent section diff (Mode B)

```
agentshift diff agent-v1.json agent-v2.json [--section <name>]
```

**Output format (rich table):**

```
agent-v1.json ↔ agent-v2.json — Section Diff

┌─────────────┬──────────────┬────────────────────────────────────────────┐
│ Section     │ Status       │ Summary                                    │
├─────────────┼──────────────┼────────────────────────────────────────────┤
│ overview    │ ✅ unchanged  │ —                                         │
│ behavior    │ ⚠️  changed   │ +3 lines, -1 line                         │
│ guardrails  │ ✅ unchanged  │ —                                         │
│ tools       │ 🆕 added     │ New section (42 chars)                     │
│ examples    │ ❌ removed   │ Was present in v1                          │
└─────────────┴──────────────┴────────────────────────────────────────────┘
```

**Section status values:**

| Status | Condition |
|--------|-----------|
| `unchanged` | Section bodies are identical after whitespace normalization |
| `changed` | Section bodies differ; summary shows approximate line delta |
| `added` | Section present in v2 but not v1 |
| `removed` | Section present in v1 but not v2 |
| `missing-in-source` | Section present in v2 only (source had no sections) |

With `--section <name>`, the output shows a full unified diff of that section body.

### 6.4 Diff implementation notes

- When one or both IRs lack `sections`, fall back to a unified diff of `system_prompt` (existing behavior, or a new plain-text diff if neither had sections).
- Whitespace normalization: strip trailing spaces per line; collapse multiple blank lines to one.
- Line delta calculation: split body by `\n`, compare lengths with `difflib.SequenceMatcher`.
- The `--section` flag implies Mode B only; error if used with Mode A (single IR + targets).

---

## 7. Backward Compatibility

### 7.1 Guarantees

1. **`sections` is always optional.** All existing IRs without `sections` remain fully valid. No validation errors, no warnings.
2. **`system_prompt` stays canonical.** Emitters MUST always work from `system_prompt` when `sections` is absent. `sections` is an optimization path, never a requirement.
3. **`ir_version` stays `"1.0"`.** Adding `sections` does not require a version bump. The schema uses `additionalProperties: false` on `persona`, so `sections` must be formally added to the schema — but the `$id` and `ir_version` remain unchanged to avoid breaking existing validators.
4. **Round-trips are preserved.** A parser that populates `sections` MUST ensure that concatenating all section bodies (with their headings) reproduces the `system_prompt` content exactly (modulo whitespace normalization).
5. **Emitters degrade gracefully.** An emitter that does not yet understand `sections` continues to use `system_prompt` and produces identical output to its current behavior.

### 7.2 Migration path

Existing users are unaffected. New parsers can opt in by calling the section-extraction utility (to be implemented in D20). The `agentshift convert` command will automatically populate `sections` when parsing markdown-based sources, unless `--no-sections` is passed.

---

## 8. Python Model Changes (for D20)

The Pydantic `Persona` class in `ir.py` should be updated as follows:

```python
class Persona(BaseModel):
    model_config = {"extra": "forbid"}

    system_prompt: str | None = None
    personality_notes: str | None = None
    language: str = "en"
    sections: dict[str, str] | None = None  # NEW: optional structured sections map
```

A utility function `extract_sections(text: str) -> dict[str, str]` should be added to a new module `src/agentshift/sections.py` (or inline in `parsers/utils.py`) implementing the algorithm in §3.1.

The function signature:

```python
def extract_sections(
    text: str,
    *,
    normalize_aliases: bool = True,
    include_preamble: bool = False,
) -> dict[str, str]:
    """Extract H2 (or H3 fallback) sections from markdown text.
    
    Returns a dict mapping canonical section slugs to their body text.
    system_prompt must be set separately — this function only builds the sections map.
    """
```

---

## 9. Test Requirements (for T13)

Tests should cover:

1. **Parser extraction — happy path:** SKILL.md with H2 headings → correct `sections` dict with canonical slugs.
2. **Parser extraction — alias normalization:** Heading `## Safety` → slug `guardrails`.
3. **Parser extraction — H3 fallback:** No H2 headings present → H3 headings extracted.
4. **Parser extraction — no headings:** Flat body → `sections` is `None` or empty dict.
5. **Parser extraction — preamble:** Content before first heading preserved in `system_prompt` only.
6. **Duplicate canonical mapping:** Two headings mapping to same canonical slug → bodies merged with warning.
7. **Bedrock emitter — guardrails routing:** When `sections.guardrails` is present, guardrail config is emitted.
8. **Bedrock emitter — no sections fallback:** When `sections` is absent, emitter uses `system_prompt` (unchanged behavior).
9. **Vertex emitter — goal/instructions split:** `sections.overview` → `goal`, rest → `instructions`.
10. **Copilot emitter — sections-aware assembly:** Correct section order and headers in `instructions`.
11. **Diff — section row in portability matrix:** When sections present, "Persona Sections" row appears.
12. **Diff — agent-to-agent:** Two IRs compared section-by-section; correct status per section.
13. **Backward compat:** IR without `sections` passes validation, all emitters produce same output as before.
14. **Round-trip:** parse → emit → parse produces equivalent `sections` map.

---

## 10. Open Questions

| # | Question | Proposed answer |
|---|----------|----------------|
| 1 | Should `sections` be ordered (insertion order) or sorted? | Insertion order preserved (Python dict, JSON object). Emitters apply canonical ordering per §5.4. |
| 2 | Max section body length? | No hard limit — `system_prompt` character limits still apply at emit time. |
| 3 | Should custom section names be allowed? | Yes — any slug matching `^[a-z][a-z0-9-]*$` is valid. Well-known names get special treatment; unknowns are appended verbatim. |
| 4 | What about YAML frontmatter in SKILL.md? | Frontmatter is already stripped before `system_prompt` is populated. Section extraction operates on the post-frontmatter body. |
| 5 | LangGraph emitter? | LangGraph uses a flat `system_message` — treat same as `system_prompt`, no section-specific routing needed in v0.2. |

---

## Appendix A — Full IR Example with Sections

```json
{
  "ir_version": "1.0",
  "name": "weather",
  "description": "Get current weather and forecasts via wttr.in",
  "version": "1.0.0",
  "persona": {
    "system_prompt": "## Overview\nI provide current weather and forecasts...\n\n## Behavior\n- Always state the location...\n\n## Guardrails\nDo not provide weather advisories as official warnings.",
    "language": "en",
    "sections": {
      "overview": "I provide current weather and forecasts using wttr.in or Open-Meteo.",
      "behavior": "- Always state the location you're reporting for.\n- Use °C by default; offer °F on request.\n- If location is ambiguous, ask for clarification before fetching.",
      "guardrails": "Do not provide weather advisories as official emergency warnings. Always recommend checking local authorities for severe weather."
    }
  },
  "tools": [],
  "metadata": {
    "source_platform": "openclaw",
    "platform_extensions": {
      "_ir": { "sections_populated": true }
    }
  }
}
```

---

## Appendix B — Section Slug Normalization Reference

```python
import re

ALIAS_MAP = {
    "about": "overview",
    "description": "overview",
    "intro": "overview",
    "introduction": "overview",
    "instructions": "behavior",
    "rules": "behavior",
    "guidelines": "behavior",
    "how-i-work": "behavior",
    "how-to-use": "behavior",
    "safety": "guardrails",
    "restrictions": "guardrails",
    "limits": "guardrails",
    "do-not": "guardrails",
    "constraints": "guardrails",
    "capabilities": "tools",
    "integrations": "tools",
    "tool-use": "tools",
    "available-tools": "tools",
    "context": "knowledge",
    "background": "knowledge",
    "data": "knowledge",
    "knowledge-base": "knowledge",
    "personality": "persona",
    "tone": "persona",
    "voice": "persona",
    "character": "persona",
    "style": "persona",
    "sample-interactions": "examples",
    "usage-examples": "examples",
    "demos": "examples",
    "when-to-use": "triggers",
    "activation": "triggers",
    "use-cases": "triggers",
    "format": "output-format",
    "output": "output-format",
    "response-format": "output-format",
    "authentication": "auth",
    "credentials": "auth",
    "setup": "auth",
}


def normalize_slug(heading: str) -> str:
    """Normalize a markdown heading to a canonical section slug."""
    slug = heading.lstrip("#").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return ALIAS_MAP.get(slug, slug)
```
