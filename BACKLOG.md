# AgentShift Backlog

## Format
| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|

**Statuses:** `ready` → `in-progress` → `pr-created` → `merged` | `blocked`
**Owners:** `@architect`, `@dev`, `@tester`, `@chief`

---

## Week 1: Foundation + IR + OpenClaw ↔ Claude Code

| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|
| A01 | P0 | @architect | merged | Design IR JSON Schema — universal agent model |
| A02 | P0 | @architect | merged | Document OpenClaw SKILL.md format spec with examples |
| A03 | P0 | @architect | merged | Document Claude Code format spec (SKILL.md + CLAUDE.md + settings.json) |
| A04 | P1 | @architect | merged | Document Copilot declarative agent manifest schema 1.6 |
| A05 | P1 | @architect | merged | Document Bedrock agent config + OpenAPI action group format |
| A06 | P1 | @architect | merged | Document Vertex AI Agent Builder config format |
| A07 | P1 | @architect | merged | Write MCP-to-OpenAPI mapping specification |
| D01 | P0 | @dev | merged | Set up Python project scaffold (pyproject.toml, src layout, CLI entry point) |
| D02 | P0 | @dev | merged | Implement IR model as Python dataclasses (based on A01 spec) |
| D03 | P0 | @dev | merged | Implement OpenClaw parser (SKILL.md → IR) |
| D04 | P0 | @dev | merged | Implement Claude Code emitter (IR → SKILL.md + CLAUDE.md) |
| D05 | P0 | @dev | merged | Implement Claude Code parser (SKILL.md + CLAUDE.md → IR) |
| D06 | P0 | @dev | merged | Implement `agentshift convert` CLI command |
| T01 | P0 | @tester | merged | Create test fixture skills (simple, tool-heavy, cron-knowledge) |
| T02 | P0 | @tester | merged | Write parser tests for OpenClaw parser |
| T03 | P0 | @tester | merged | Write round-trip tests (OpenClaw → IR → OpenClaw) |
| T04 | P0 | @tester | merged | Copy pregnancy-companion as integration test fixture |

## Week 2: Cloud Emitters

| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|
| D07 | P1 | @dev | merged | Implement Copilot emitter (IR → .agent.md) |
| D08 | P1 | @dev | merged | Implement Bedrock emitter (IR → instruction + OpenAPI + CloudFormation) |
| D09 | P1 | @dev | merged | Implement Vertex AI emitter (IR → Agent Builder config) |
| D10 | P1 | @dev | merged | Handle platform constraints (instruction length limits, etc.) |
| T05 | P1 | @tester | merged | Write emitter tests for all cloud targets |
| T06 | P1 | @tester | merged | Validate generated Copilot manifest against JSON schema |

## Week 3: Diff + Validate

| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|
| D11 | P1 | @dev | merged | Implement MCP-to-OpenAPI converter |
| D12 | P1 | @dev | merged | Implement `agentshift diff` command with rich table output |
| D13 | P1 | @dev | merged | Implement `agentshift validate` command |
| D14 | P1 | @dev | merged | Generate auth/trigger/data binding stubs with TODO comments |
| T07 | P1 | @tester | merged | Write diff accuracy tests |
| T08 | P1 | @tester | merged | Write CLI integration tests (end-to-end) |
| T09 | P1 | @tester | merged | Full integration test: pregnancy-companion → all 4 targets |
