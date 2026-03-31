# Copilot → IR Parser Spec

**Spec ID:** A15
**Status:** Canonical
**Author:** @architect
**Closes:** A15 (Week 8 backlog)
**Reverse of:** `specs/copilot-agent-format.md` (emitter direction)
**Implements:** D26

---

## 1. Overview

The Copilot parser converts GitHub Copilot `.agent.md` files back into an AgentShift IR. This is
the reverse of the Copilot emitter (`src/agentshift/emitters/copilot.py`).

**Input artifacts:**

| File | Role | Required? |
|------|------|-----------|
| `<slug>.agent.md` | Agent definition (YAML frontmatter + markdown body) | Primary |
| `README.md` | Setup documentation (may contain MCP server config) | Optional |

**Primary input format:** `.agent.md` — YAML frontmatter followed by a markdown body containing
the agent's system prompt and governance sections.

---

## 2. Input Format Reference

### 2.1 `.agent.md` — Copilot Agent File

A `.agent.md` file consists of YAML frontmatter delimited by `---` lines, followed by a markdown
body that serves as the agent's system prompt / instruction set.

```markdown
---
name: "pregnancy-companion"
description: "24/7 pregnancy companion"
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "Claude Opus 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - execute/runInTerminal
  - read/readFile
  - edit/editFiles
---

<!-- MCP: configure slack server separately in VS Code settings -->

You are a warm, knowledgeable pregnancy companion...

## Guardrails

- Never provide medical diagnoses or treatment recommendations.

## Governance Constraints (Elevated)

<!-- These constraints were elevated from enforcement-level (L2/L3)
     to prompt-level (L1) because GitHub Copilot does not natively support
     the original enforcement mechanism. -->

- Do NOT use the dangerous_tool tool. It is disabled.
```

### 2.2 `README.md` — Setup Documentation

The emitter generates a `README.md` alongside the `.agent.md` file. When present, the parser
extracts MCP server configuration details from fenced JSON blocks under the `## MCP Servers Required`
heading.

```markdown
## MCP Servers Required

```json
"github.copilot.chat.agent.mcp.server": {
  "slack": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-slack"]
  }
}
```​
```

---

## 3. Copilot → IR Field Mapping

### 3.1 Core fields (from YAML frontmatter)

| Copilot field | IR field | Transformation |
|---------------|----------|----------------|
| `name` | `name` | Direct; strip surrounding quotes |
| `description` | `description` | Direct; strip surrounding quotes |
| `model` | `metadata.platform_extensions.copilot.model` | Preserve full list for round-trip |
| `tools` | `ir.tools` | Map each tool ID to IR tool (see §4) |

### 3.2 Platform metadata

```python
ir.metadata.source_platform = "copilot"
ir.metadata.platform_extensions["copilot"] = {
    "model": model_list,           # e.g. ["Claude Sonnet 4.6 (copilot)", ...]
    "source_file": filename,       # e.g. "pregnancy-companion.agent.md"
}
```

### 3.3 Markdown body → `persona.system_prompt` + `persona.sections`

1. **Full body capture:** Everything after the closing `---` of the frontmatter becomes the
   candidate system prompt text, with leading/trailing whitespace stripped.

2. **MCP comment removal:** Strip `<!-- MCP: configure ... -->` comment lines from the body
   before storing as `system_prompt`. These are parsed separately (see §5).

3. **Governance section removal:** Strip `## Guardrails` and `## Governance Constraints (Elevated)`
   sections from the body before storing as `system_prompt`. These are parsed separately (see §6).

4. **Section extraction:** Run the section extractor (`extract_sections()`) on the remaining
   body text. If the body contains `## Heading` markdown structure, populate `persona.sections`.

5. **Language detection:** If the body contains a language directive (e.g., "Respond in Spanish"),
   set `persona.language` accordingly. Default to `"en"`.

**Important:** The `system_prompt` stored in the IR should be the "clean" prompt text — without
MCP comments or governance sections. This matches the original IR before emission, enabling
round-trip fidelity.

---

## 4. Tool ID → IR Tool Mapping

The parser reverses the mapping performed by `_build_tools()` in the emitter.

### 4.1 Standard tool ID mapping

| Copilot Tool ID | IR `Tool.kind` | IR `Tool.name` | IR `Tool.description` |
|-----------------|----------------|-----------------|----------------------|
| `execute/runInTerminal` | `shell` | `bash` | `"Run shell commands"` |
| `read/readFile` | `builtin` | `read` | `"Read files from the workspace"` |
| `edit/editFiles` | `builtin` | `edit` | `"Create, modify, or delete files"` |
| `web` | `builtin` | `web_fetch` | `"Fetch web pages or call HTTP APIs"` |
| `search` | `builtin` | `web_search` | `"Search the web"` |
| `execute/runTask` | `builtin` | `run_task` | `"Run a VS Code task by name"` |
| `execute/createAndRunTask` | `builtin` | `create_and_run_task` | `"Create and run a VS Code task"` |
| `execute/getTerminalOutput` | `builtin` | `get_terminal_output` | `"Read output from last terminal run"` |
| `read/problems` | `builtin` | `read_problems` | `"Read compiler/linter diagnostics"` |
| `read/terminalLastCommand` | `builtin` | `terminal_last_command` | `"Read last terminal command + output"` |
| `read/getTaskOutput` | `builtin` | `get_task_output` | `"Read output from a named task"` |
| `agent` | `builtin` | `agent` | `"Invoke another Copilot agent"` |
| `todo` | `builtin` | `todo` | `"Manage VS Code TODO items"` |
| `vscode/runCommand` | `builtin` | `vscode_run_command` | `"Run a VS Code command by ID"` |
| `vscode/getProjectSetupInfo` | `builtin` | `vscode_project_info` | `"Read project language/framework info"` |

### 4.2 GitHub extension tool IDs

| Copilot Tool ID | IR `Tool.kind` | IR `Tool.name` | IR `Tool.description` |
|-----------------|----------------|-----------------|----------------------|
| `github.vscode-pull-request-github/doSearch` | `builtin` | `github_search` | `"Search GitHub issues, PRs, code"` |
| `github.vscode-pull-request-github/activePullRequest` | `builtin` | `github_active_pr` | `"Get context of the active PR"` |

### 4.3 Platform availability

All tools parsed from a `.agent.md` file should include `"copilot"` in their
`platform_availability` list.

### 4.4 Deduplication

The emitter may produce both `web` and `search` from a single IR tool like `web_search`. When
the parser encounters both `web` and `search`, it should produce two separate IR tools (they
represent distinct capabilities on the Copilot side), each with `platform_availability: ["copilot"]`.

### 4.5 Unknown tool IDs

If a tool ID is not in the known mapping table, create a tool with:
```python
Tool(
    name=tool_id.replace("/", "_"),
    description=f"Copilot tool: {tool_id}",
    kind="unknown",
    platform_availability=["copilot"],
)
```

---

## 5. MCP Tool Extraction

MCP tools are encoded as HTML comments in the markdown body by the emitter:

```
<!-- MCP: configure <name> server separately in VS Code settings -->
```

### 5.1 Parsing algorithm

1. Scan the markdown body for lines matching the pattern:
   ```python
   MCP_COMMENT_RE = re.compile(
       r'<!--\s*MCP:\s*configure\s+(\S+)\s+server\s+separately.*?-->',
       re.IGNORECASE
   )
   ```

2. For each match, extract the server name and create an IR tool:
   ```python
   Tool(
       name=mcp_name,
       description=f"MCP server: {mcp_name}",
       kind="mcp",
       platform_availability=["copilot"],
   )
   ```

### 5.2 README.md enrichment

If `README.md` is present and contains an `## MCP Servers Required` section, parse the JSON
code block to extract server names and configuration hints. Update the tool's `description`
with the package name if available (e.g., `"MCP server: slack (@modelcontextprotocol/server-slack)"`).

### 5.3 Auth from README

If the README contains environment variable references for MCP servers, create a `ToolAuth`:
```python
ToolAuth(
    type="config_key",
    config_key=f"channels.{mcp_name}",
)
```

---

## 6. Governance Extraction

The Copilot emitter writes governance data into two markdown sections:

### 6.1 `## Guardrails` → `governance.guardrails`

Parse the `## Guardrails` section. Each bullet point (`- `) becomes a `Guardrail`:

```python
Guardrail(
    id=f"G{n:03d}",
    text=bullet_text.strip(),
    category=infer_category(bullet_text),    # see §6.3
    severity=infer_severity(bullet_text),    # see §6.3
)
```

### 6.2 `## Governance Constraints (Elevated)` → governance (best-effort)

This section contains L2/L3 governance constraints that were elevated to prompt-level (L1)
by the elevation engine because Copilot lacks native support. The parser should:

1. Parse each bullet point.
2. Attempt to reverse the elevation instruction templates (see `governance-ir-schema.md` Appendix A):

| Elevated instruction pattern | Reverse to |
|------------------------------|-----------|
| `"Do NOT use the {tool_name} tool. It is disabled."` | `ToolPermission(tool_name=..., enabled=False, access="disabled")` |
| `"When using {tool_name}, NEVER access paths matching: {pattern}"` | `ToolPermission(tool_name=..., deny_patterns=[pattern])` |
| `"The {tool_name} tool is READ-ONLY..."` | `ToolPermission(tool_name=..., access="read-only")` |
| `"Rate limit for {tool_name}: do not exceed {rate_limit}."` | `ToolPermission(tool_name=..., rate_limit=rate_limit)` |
| `"Maximum value constraint for {tool_name}: {max_value}."` | `ToolPermission(tool_name=..., max_value=max_value)` |
| `"The {tool_name} tool may ONLY be used for paths matching: {pattern}"` | `ToolPermission(tool_name=..., allow_patterns=[pattern])` |
| `"CONTENT POLICY: {description}"` | `PlatformAnnotation(kind="content_filter", description=...)` |
| `"PII PROTECTION: {description}"` | `PlatformAnnotation(kind="pii_detection", description=...)` |
| `"DENIED TOPIC: {description}"` | `PlatformAnnotation(kind="denied_topics", description=...)` |
| `"GROUNDING REQUIREMENT: {description}"` | `PlatformAnnotation(kind="grounding_check", description=...)` |

3. If a bullet does not match any known template, add it as a `Guardrail` with
   `category="general"` (treat as L1 — cannot determine original layer).

### 6.3 Category and severity inference

Reuse the same heuristic as the Bedrock parser (see `bedrock-parser-spec.md` §4):

**Category inference:**

| Keyword in text | Inferred category |
|-----------------|-------------------|
| `diagnos`, `medic`, `prescri`, `treatment` | `safety` |
| `PII`, `personal`, `identif`, `private`, `confidential` | `privacy` |
| `GDPR`, `HIPAA`, `COPPA`, `regulatory`, `legal`, `comply` | `compliance` |
| `bias`, `discriminat`, `fair`, `honest` | `ethical` |
| `topic`, `subject`, `discuss`, `respond only` | `scope` |
| (default) | `general` |

**Severity inference:**
- Text contains `"critical"`, `"never"`, `"must not"` → `critical`
- Text contains `"always"`, `"prohibited"` → `high`
- Default → `medium`

---

## 7. System Prompt → L1 Guardrail Heuristic

In addition to explicit `## Guardrails` sections, the parser SHOULD scan the clean `system_prompt`
text for guardrail-like sentences using the same heuristic as the Bedrock parser:

**Trigger patterns (case-insensitive):**
- `"never "` at word boundary
- `"do not "` at word boundary
- `"always "` at word boundary
- `"must not "` at word boundary
- `"avoid "` at word boundary
- `"prohibited"`, `"forbidden"`, `"not allowed"`

Extracted guardrails from the body are **deduplicated** against those already extracted from the
`## Guardrails` section (compare normalized text). Only unique guardrails are added.

---

## 8. Parser Input Resolution

### 8.1 Finding the `.agent.md` file

The parser accepts a directory path and auto-discovers input files:

1. Glob for `*.agent.md` files in the directory.
2. If exactly one is found, use it as the primary input.
3. If multiple are found, parse each into a separate IR and return a list. The CLI should handle
   multi-agent directories by prompting or processing all.
4. If none found, raise `ParseError("No .agent.md files found in {dir}")`.

### 8.2 Finding `README.md`

Look for `README.md` in the same directory as the `.agent.md` file. If present, use it for
MCP server enrichment (§5.2).

### 8.3 Frontmatter parsing

1. Read the file content.
2. Split on the first two `---` lines to extract the YAML frontmatter block.
3. Parse the YAML block using a safe YAML loader.
4. If frontmatter is missing or malformed, fall back:
   - `name` → derive from filename slug (e.g., `pr-reviewer.agent.md` → `"pr-reviewer"`)
   - `description` → first non-heading line of the markdown body
   - `tools` → empty list

---

## 9. Parser Entry Point

The parser is implemented in `src/agentshift/parsers/copilot.py`.

```python
def parse(input_dir: Path) -> AgentIR:
    """Parse Copilot agent artifacts from a directory into an AgentIR.

    Reads:
    - *.agent.md (primary — exactly one expected)
    - README.md (optional — MCP server enrichment)

    Raises ParseError if no .agent.md files are found.
    """
```

**Alternative entry points:**

```python
def parse_agent_md(content: str, filename: str = "agent.agent.md") -> AgentIR:
    """Parse a single .agent.md file content string into an AgentIR."""

def parse_multiple(input_dir: Path) -> list[AgentIR]:
    """Parse all .agent.md files in a directory, returning one IR per file."""
```

---

## 10. CLI Integration

```bash
# Convert from Copilot agent directory
agentshift convert ./copilot-output/ --from copilot --to openclaw

# Convert a single .agent.md file
agentshift convert ./pr-reviewer.agent.md --from copilot --to ir

# Diff Copilot agent against OpenClaw source
agentshift diff ./copilot-output/ --from copilot ./my-skill/ --from openclaw

# Audit governance preservation
agentshift audit ./copilot-output/ --from copilot --targets bedrock,vertex
```

---

## 11. Validation Notes

The parser output MUST pass `agentshift validate`. Key checks:

1. `ir.name` is non-empty.
2. `ir.description` is non-empty.
3. All `tool.name` values are unique within the IR.
4. `governance.guardrails[].id` values are unique.
5. `governance.platform_annotations[].id` values are unique.

---

## 12. Round-Trip Fidelity

A round-trip is: `openclaw → copilot → openclaw`.

**Guaranteed to survive:**
- Agent `name` and `description`
- `persona.system_prompt` (clean body text, excluding governance sections)
- `persona.sections` (if body contains `## Heading` markdown structure)
- Tool names and kinds (via the mapping table)
- MCP tool names (via comment extraction)
- L1 guardrails (from `## Guardrails` section)
- Elevated L2/L3 governance (best-effort reverse of elevation templates)

**Known lossy fields:**
- `tools[].description` — replaced with generic descriptions from the mapping table; original
  descriptions from the IR are not preserved in `.agent.md` tool IDs
- `tools[].parameters` — tool IDs carry no parameter information
- `tools[].auth` — not stored in `.agent.md`; partial recovery from README
- `triggers` — not preserved (Copilot has no trigger mechanism)
- `install` — not preserved (not applicable to Copilot)
- `knowledge` — partially inferred (presence of `read/readFile` suggests file access, but
  specific paths/descriptions are lost)
- `constraints.supported_os` — not stored
- `constraints.required_bins` — not stored
- `metadata.emoji` — not stored
- `metadata.tags` — not stored
- `model` list — preserved in `platform_extensions.copilot.model` but not in a standard IR field

**Improvement notes for emitter:** To improve round-trip fidelity, the emitter could embed
structured metadata in an HTML comment block:
```
<!-- AGENTSHIFT_META: {"tools": [...], "knowledge": [...]} -->
```
This is not currently implemented but would allow lossless round-trips.

---

## 13. Edge Cases

### 13.1 Missing frontmatter

If the `.agent.md` file has no YAML frontmatter (no `---` delimiters), treat the entire file
as the markdown body. Derive `name` from the filename and `description` from the first paragraph.

### 13.2 Empty tools list

If `tools: []` or `tools` is absent in frontmatter, produce an IR with an empty `tools` list.

### 13.3 Multiple `.agent.md` files

When a directory contains multiple `.agent.md` files, `parse()` should use the first one found
(sorted alphabetically). Use `parse_multiple()` to process all files.

### 13.4 Non-AgentShift-generated files

The parser must handle `.agent.md` files not generated by AgentShift:
- No `<!-- MCP: ... -->` comments → no MCP tools extracted
- No `## Guardrails` section → no explicit governance; rely on system prompt heuristic
- No `## Governance Constraints (Elevated)` → no L2/L3 recovery
- Unknown tool IDs → mapped via the fallback in §4.5

### 13.5 Quoted vs unquoted frontmatter values

Both `name: "My Agent"` and `name: My Agent` should be accepted. The YAML parser handles this
natively; the spec documents it for implementer awareness.

### 13.6 Multiline description in frontmatter

YAML multiline scalars (`|`, `>`) in the `description` field should be collapsed to a single
line for the IR `description` field.

---

## Appendix A — Regex Patterns

```python
import re

# Frontmatter extraction
FRONTMATTER_RE = re.compile(
    r'^---\s*\n(.*?)\n---\s*\n',
    re.DOTALL
)

# MCP comment extraction
MCP_COMMENT_RE = re.compile(
    r'<!--\s*MCP:\s*configure\s+(\S+)\s+server\s+separately.*?-->',
    re.IGNORECASE
)

# Guardrails section extraction
GUARDRAILS_SECTION_RE = re.compile(
    r'^##\s+Guardrails\s*\n(.*?)(?=^##\s|\Z)',
    re.MULTILINE | re.DOTALL
)

# Elevated governance section extraction
ELEVATED_SECTION_RE = re.compile(
    r'^##\s+Governance\s+Constraints\s+\(Elevated\)\s*\n(.*?)(?=^##\s|\Z)',
    re.MULTILINE | re.DOTALL
)

# Bullet point extraction
BULLET_RE = re.compile(r'^-\s+(.+)$', re.MULTILINE)

# Elevation template reversal patterns
DISABLED_TOOL_RE = re.compile(
    r'Do NOT use the (\S+) tool\. It is disabled\.',
    re.IGNORECASE
)
DENY_PATTERN_RE = re.compile(
    r'When using (\S+), NEVER access paths matching:\s*(.+)',
    re.IGNORECASE
)
READ_ONLY_RE = re.compile(
    r'The (\S+) tool is READ-ONLY',
    re.IGNORECASE
)
RATE_LIMIT_RE = re.compile(
    r'Rate limit for (\S+): do not exceed (.+)\.',
    re.IGNORECASE
)
MAX_VALUE_RE = re.compile(
    r'Maximum value constraint for (\S+): (.+)\.',
    re.IGNORECASE
)
ALLOW_PATTERN_RE = re.compile(
    r'The (\S+) tool may ONLY be used for paths matching:\s*(.+)',
    re.IGNORECASE
)
CONTENT_POLICY_RE = re.compile(r'^CONTENT POLICY:\s*(.+)', re.IGNORECASE)
PII_PROTECTION_RE = re.compile(r'^PII PROTECTION:\s*(.+)', re.IGNORECASE)
DENIED_TOPIC_RE = re.compile(r'^DENIED TOPIC:\s*(.+)', re.IGNORECASE)
GROUNDING_REQ_RE = re.compile(r'^GROUNDING REQUIREMENT:\s*(.+)', re.IGNORECASE)
```

---

## Appendix B — Complete Parse Example

### Input (`pregnancy-companion.agent.md`):

```markdown
---
name: "pregnancy-companion"
description: "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey"
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "Claude Opus 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - execute/runInTerminal
  - read/readFile
  - edit/editFiles
---

<!-- MCP: configure slack server separately in VS Code settings -->

You are a warm, knowledgeable pregnancy companion...

## Behavior
- Track symptoms and appointments using local files.
- Provide weekly development updates.

## Guardrails

- Never provide medical diagnoses or treatment recommendations.
- Do not share personally identifiable information.

## Governance Constraints (Elevated)

<!-- These constraints were elevated from enforcement-level (L2/L3)
     to prompt-level (L1) because GitHub Copilot does not natively support
     the original enforcement mechanism. -->

- The filesystem tool is READ-ONLY. Do NOT use it to write, modify, or delete any data.
- DENIED TOPIC: Discussion of competitor products
```

### Output IR:

```json
{
  "ir_version": "1.0",
  "name": "pregnancy-companion",
  "description": "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey",
  "persona": {
    "system_prompt": "You are a warm, knowledgeable pregnancy companion...\n\n## Behavior\n- Track symptoms and appointments using local files.\n- Provide weekly development updates.",
    "sections": {
      "behavior": "- Track symptoms and appointments using local files.\n- Provide weekly development updates."
    },
    "language": "en"
  },
  "tools": [
    {
      "name": "bash",
      "description": "Run shell commands",
      "kind": "shell",
      "platform_availability": ["copilot"]
    },
    {
      "name": "read",
      "description": "Read files from the workspace",
      "kind": "builtin",
      "platform_availability": ["copilot"]
    },
    {
      "name": "edit",
      "description": "Create, modify, or delete files",
      "kind": "builtin",
      "platform_availability": ["copilot"]
    },
    {
      "name": "slack",
      "description": "MCP server: slack",
      "kind": "mcp",
      "platform_availability": ["copilot"]
    }
  ],
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
        "text": "Do not share personally identifiable information.",
        "category": "privacy",
        "severity": "medium"
      }
    ],
    "tool_permissions": [
      {
        "tool_name": "filesystem",
        "enabled": true,
        "access": "read-only",
        "notes": "Elevated from L2 — recovered from Copilot prompt instruction"
      }
    ],
    "platform_annotations": [
      {
        "id": "PA-001",
        "kind": "denied_topics",
        "description": "Discussion of competitor products",
        "platform_target": "any",
        "config": {}
      }
    ]
  },
  "metadata": {
    "source_platform": "copilot",
    "source_file": "pregnancy-companion.agent.md",
    "platform_extensions": {
      "copilot": {
        "model": [
          "Claude Sonnet 4.6 (copilot)",
          "Claude Opus 4.6 (copilot)",
          "GPT-5.3-Codex"
        ],
        "source_file": "pregnancy-companion.agent.md"
      }
    }
  }
}
```
