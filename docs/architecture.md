# Architecture: How AgentShift Works

---

## The IR concept

Without a shared intermediate format, converting N platforms to N platforms requires N² direct converters — each one hand-coded, each one a maintenance burden.

AgentShift solves this with an **Intermediate Representation (IR)**: a single canonical agent model that every parser writes to and every emitter reads from.

```
N parsers × N emitters
        ↓
N parsers + N emitters (via IR)
```

Adding a new platform means writing **one parser** (if you want to read it) and/or **one emitter** (if you want to write it). No other code changes.

---

## Pipeline

```
Input files                    IR fields                     Output files
──────────────────────────     ──────────────────────────    ─────────────────────────
SKILL.md · CLAUDE.md      →   identity                  →   CLAUDE.md
manifest.json · jobs.json  →   tools                    →   settings.json
instruction.txt            →   knowledge                 →   github.agent.md
                           →   triggers                  →   bedrock-agent.json
                           →   constraints               →   vertex-agent.yaml

        Parser                     IR (in memory)                  Emitter
```

**Concrete example** — converting the `github` skill:

```
~/.openclaw/skills/github/
├── SKILL.md          ← Parser reads: identity, tools, constraints
└── jobs.json         ← Parser reads: cron triggers

        ↓  OpenClaw parser

IR {
  name: "github",
  description: "GitHub operations via gh CLI...",
  persona: { system_prompt: "# GitHub Skill\n..." },
  tools: [{ name: "gh", kind: "shell" }, { name: "git", kind: "shell" }],
  triggers: [],
  constraints: { required_bins: ["gh"] }
}

        ↓  Claude Code emitter          ↓  Copilot emitter

github-claude/                          github-copilot/
├── CLAUDE.md                           ├── github.agent.md
└── settings.json                       └── README.md
```

---

## IR field reference

| Field | Type | Description |
|---|---|---|
| `ir_version` | string | Always `"1.0"` for this revision |
| `name` | string | Lowercase slug, e.g. `"github"` |
| `description` | string | One-line summary; used as skill trigger text |
| `version` | string | Semver, e.g. `"1.0.0"` |
| `author` | string | Author or owner |
| `persona.system_prompt` | string | Full system / instruction prompt |
| `persona.personality_notes` | string | Tone and style notes (informational) |
| `persona.language` | string | BCP-47 language code, default `"en"` |
| `tools[]` | array | Capabilities: MCP, shell, OpenAPI, builtin |
| `tools[].name` | string | Tool identifier, e.g. `"gh"`, `"slack"` |
| `tools[].kind` | enum | `mcp \| openapi \| shell \| builtin \| function` |
| `tools[].endpoint` | string | MCP server URI or OpenAPI base URL |
| `knowledge[]` | array | Data sources: files, directories, URLs |
| `knowledge[].kind` | enum | `file \| directory \| url \| vector_store \| database \| s3` |
| `knowledge[].load_mode` | enum | `always \| on_demand \| indexed` |
| `triggers[]` | array | Activation events: cron, webhook, message |
| `triggers[].kind` | enum | `cron \| webhook \| message \| event \| manual` |
| `triggers[].cron_expr` | string | 5-field cron expression |
| `triggers[].message` | string | Prompt injected when trigger fires |
| `constraints.supported_os` | array | `["darwin", "linux", "windows"]` |
| `constraints.required_bins` | array | CLI binaries that must be present |
| `constraints.guardrails` | array | Named safety guardrails |
| `metadata.source_platform` | enum | Where this IR was parsed from |
| `metadata.emoji` | string | Display emoji |

Full schema: [`specs/ir-schema.json`](../specs/ir-schema.json)

---

## Per-platform mapping

| IR field | OpenClaw | Claude Code | Copilot | Bedrock | Vertex AI |
|---|---|---|---|---|---|
| `name` | `SKILL.md` frontmatter `name` | `CLAUDE.md` H1 | `name` in frontmatter | agent name | display name |
| `description` | `SKILL.md` frontmatter `description` | First paragraph | `description` in frontmatter | description | description |
| `persona.system_prompt` | `SKILL.md` body | `CLAUDE.md` body | agent body | instruction field | instruction |
| `tools[shell]` | `metadata.openclaw.requires.bins` | `Bash(<bin>:*)` in `settings.json` | `execute/runInTerminal` | action group | tool config |
| `tools[mcp]` | `TOOLS.md` MCP entries | `mcp__<name>__*` in `settings.json` | manual MCP config in VS Code | — | — |
| `knowledge[file]` | `knowledge/` directory | `Read(<path>)` permission | `read/readFile` tool | knowledge base | data store |
| `triggers[cron]` | `jobs.json` schedule | Cloud Scheduled Tasks | ❌ not supported | EventBridge | Cloud Scheduler |
| `constraints.supported_os` | `metadata.openclaw.os` | `settings.json` `supportedOs` | — | — | — |

---

## How to add a new platform

Each platform needs up to three files under `src/agentshift/platforms/<platform>/`:

```
src/agentshift/platforms/myplatform/
├── __init__.py       ← registers the platform slug
├── parser.py         ← reads platform files → IR (optional, if you want to read from it)
└── emitter.py        ← IR → platform files (optional, if you want to write to it)
```

**Parser** (`parser.py`):
- Implement `parse(skill_dir: Path) -> IR`
- Read whatever files the platform uses
- Map fields to the IR schema above

**Emitter** (`emitter.py`):
- Implement `emit(ir: IR, output_dir: Path) -> None`
- Write whatever files the platform expects
- Only map fields that the platform supports; document gaps

**Register**:
```python
# src/agentshift/platforms/myplatform/__init__.py
PLATFORM_SLUG = "myplatform"
PARSER = "agentshift.platforms.myplatform.parser:MyPlatformParser"
EMITTER = "agentshift.platforms.myplatform.emitter:MyPlatformEmitter"
```

Then add `myplatform` to the `[project.entry-points]` section in `pyproject.toml`.

Open a [Platform Request](https://github.com/ogkranthi/agentshift/issues/new?template=platform_request.yml) to discuss a new target before starting.
