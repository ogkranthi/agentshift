# Changelog

All notable changes to AgentShift are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.4.0] — 2026-04-03

Week 8 release — Copilot parser + A2A Agent Card emitter + local agent registry (v0.4).

### Added
- **Copilot parser** (`--from copilot`) — reads `.agent.md` files (YAML frontmatter + markdown
  body) and optional `manifest.json`/`README.md` and reconstructs an `AgentIR`
  - Parses Copilot-specific tool IDs (e.g. `execute/runInTerminal` → `bash`) via a standard
    mapping table
  - Extracts MCP server references from `<!-- MCP: configure X server separately -->` comments
  - Reconstructs `Guardrail` objects from `## Guardrails` sections
  - Recovers elevated governance constraints from `## Governance Constraints (Elevated)` sections
  - Heuristic reversal of elevation templates (disabled tools, deny patterns, rate limits, etc.)
- **A2A Agent Card emitter** — generates `agent-card.json` conforming to the A2A Agent Card
  specification (google.github.io/a2a)
  - Maps IR identity, capabilities, and tools to A2A `AgentCard` schema fields
  - Exports governance guardrails as A2A capability annotations
  - Generates `README.md` with manual integration instructions
- **`agentshift registry` command** — local agent registry with drift detection
  - `registry register <path>` — register an agent directory with snapshot
  - `registry list` — list all registered agents with status
  - `registry diff <name>` — detect drift between registered snapshot and current state
  - `registry export` — export registry as JSON
  - Persistent JSON store at `~/.agentshift/registry.json`

### Changed
- **Supported platforms table** updated: Copilot parser now `✅`, A2A added as new row
- Version bumped to `0.4.0`

---

## [0.3.0] — 2026-03-28

Week 7 release — Governance framework + cloud parsers (Bedrock and Vertex AI).

### Added
- **Governance IR layer** — three-layer governance model (L1 guardrails, L2 tool permissions,
  L3 platform annotations) integrated into `AgentIR.governance`
- **AWS Bedrock parser** (`--from bedrock`) — reads `bedrock-agent.json`,
  `cloudformation.yaml`, `instruction.txt`, `openapi.json`, `guardrail-config.json` (any
  combination) and reconstructs an AgentIR with tools, knowledge sources, and L1 guardrails
  - Detects and strips AgentShift instruction truncation notices
  - Heuristic L1 guardrail classification from `guardrail-config.json` topic policies
  - Tool reconstruction from OpenAPI action-group schemas
- **Vertex AI parser** (`--from vertex`) — reads `agent.json` and optional `tools.json`
  and reconstructs an AgentIR
  - Reconstructs `system_prompt` from `goal` + `instructions` fields
  - Recovers structured `persona.sections` from linearized `"SectionName:\ncontent"` patterns
  - Detects tool kind (function / OpenAPI / data store) and routes data store tools to
    `ir.knowledge`
  - Reconstructs auth from Vertex `authentication` blocks (API key, OAuth2, service account)
  - Heuristic L1 guardrail extraction from instruction strings
- **Shared parser utilities** (`parsers/utils.py`) — `slugify`, `infer_guardrail_category`,
  `infer_guardrail_severity`, `extract_guardrails_from_text`, `is_todo_placeholder`
- **CLI support** for `--from bedrock` and `--from vertex` on `convert`, `diff`, and `audit`
  commands

### Changed
- Version bumped to `0.3.0`

---

## [1.0.0] — 2026-03-26

First stable release. Full Week 3 + Week 4 feature set.

### Added
- **Error handling polish** — structured, user-friendly errors across CLI and parsers
  - `--verbose` / `-V` flag on all commands for full debug tracebacks
  - "Did you mean X?" suggestions for unknown platform names (using `difflib`)
  - Explicit check that source directory exists before parsing
  - Clear guidance when `SKILL.md` is missing or empty
  - Graceful handling of malformed YAML frontmatter in `SKILL.md`
  - Per-emitter error isolation in `convert --to all` (one failure won't abort others)
  - Validate target and source-path existence in `validate` command
- **Examples directory** — pregnancy-companion converted to all 5 targets, updated `examples/README.md`
  with diff and validate showcase commands

### Changed
- Version bumped to `1.0.0`; PyPI classifier updated to `Production/Stable`

---

## [0.3.0]

### Added
- `agentshift validate` command — validates generated configs against platform JSON schemas
- Vertex AI emitter (`--to vertex`) with Agent Builder YAML config
- Microsoft 365 Copilot emitter (`--to m365`) with declarative agent manifest
- Comprehensive emitter test suite (427 tests passing)
- MCP-to-OpenAPI converter (`agentshift mcp-to-openapi`)
- Auth/trigger/data binding stub generator

---

## [0.2.1]

### Fixed
- Microsoft 365 manifest field corrections (schema 1.6 compliance)
- Copilot `instructions` field length enforcement

---

## [0.2.0]

### Added
- AWS Bedrock emitter (instruction file + OpenAPI action group + CloudFormation template)
- `agentshift diff` command — portability matrix with Rich table output
- Platform constraint model (instruction length limits, tool type restrictions)

---

## [0.1.0]

### Added
- Project scaffold: `pyproject.toml`, `src/` layout, Hatch build system
- Intermediate Representation (IR) model (`agentshift.ir`) as Python dataclasses
- OpenClaw SKILL.md parser (`--from openclaw`)
- Claude Code emitter (`--to claude-code`) producing `SKILL.md` + `CLAUDE.md`
- Claude Code parser (`--from claude-code`)
- GitHub Copilot emitter (`--to copilot`) producing `.github/copilot-instructions.md`
- `agentshift convert` CLI command with `--to all` support
- Test fixtures: simple, tool-heavy, cron-knowledge, pregnancy-companion
