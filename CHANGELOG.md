# Changelog

All notable changes to AgentShift are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

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
