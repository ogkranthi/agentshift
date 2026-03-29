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

## Week 4: Polish + Release

| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|
| D15 | P1 | @dev | merged | Error handling polish — structured errors, edge cases, helpful messages |
| D16 | P1 | @dev | merged | PyPI release prep — version 1.0.0, classifiers, CHANGELOG.md |
| D17 | P1 | @dev | merged | Examples directory — convert pregnancy-companion to all targets, document results |
| T10 | P1 | @tester | merged | Smoke test generated configs against real platform schemas |
| A08 | P2 | @architect | merged | Draft CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md |

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

## Week 6: v0.2 — Persona Sections + Smarter Emitters

| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|
| A11 | P1 | @architect | merged | Spec persona.sections schema — structured prompt sections for IR v0.2 |
| D20 | P1 | @dev | merged | Add persona.sections to IR model + update parsers to populate from headings |
| D21 | P1 | @dev | merged | Update emitters (Bedrock, Vertex, diff) to use persona.sections |
| T13 | P1 | @tester | merged | Write tests for persona.sections — parser detection, emitter mapping, diff |

## Week 5: Ecosystem + LangGraph + GitHub Action

| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|
| A09 | P1 | @architect | merged | Research and document LangGraph agent format spec (graph config, tools, state schema) |
| A10 | P2 | @architect | merged | Draft IR spec as "Agent Portability Format" — publishable standalone document |
| D18 | P1 | @dev | merged | Implement LangGraph emitter (IR → LangGraph graph config + tools + README) |
| D19 | P1 | @dev | merged | GitHub Action: auto-generate cloud configs when SKILL.md changes (CI/CD integration) |
| T11 | P1 | @tester | merged | Write tests for LangGraph emitter (fixture + round-trip + integration) |
| T12 | P1 | @tester | merged | Add LangGraph to full integration test (pregnancy-companion → langgraph) |

## Week 7: Governance Framework + Cloud Parsers (v0.3)

> Context: Governance system (L1/L2/L3 IR fields, audit engine, elevation) was added as untracked
> work supporting a research paper. This week formalises it with specs, tests, reverse-direction
> parsers for cloud platforms, and a CHANGELOG bump to v0.3.0.

| ID | Priority | Owner | Status | Title |
|----|----------|-------|--------|-------|
| A12 | P1 | @architect | ready | Spec Governance IR schema — L1/L2/L3 layers, GPR/CFS scoring definitions, elevation rules |
| A13 | P1 | @architect | in-progress | Research and document Bedrock parser format (reverse: Bedrock → IR) |
| A14 | P1 | @architect | ready | Research and document Vertex AI parser format (reverse: Vertex → IR) |
| D22 | P1 | @dev | ready | Implement Bedrock parser (bedrock-agent.json + OpenAPI + instruction.txt → IR) |
| D23 | P1 | @dev | ready | Implement Vertex AI parser (agent.json + tool definitions → IR) |
| D24 | P1 | @dev | ready | Add `--from bedrock` and `--from vertex` to convert/diff/audit CLI commands |
| D25 | P1 | @dev | ready | Bump version to 0.3.0 — update CHANGELOG.md, pyproject.toml, add governance to README |
| T14 | P1 | @tester | ready | Write tests for governance extraction (Guardrail classification, ToolPermission, L3 annotations) |
| T15 | P1 | @tester | ready | Write tests for audit engine (GPR-L1/L2/L3 scoring, elevation tracking, CSV/JSON export) |
| T16 | P1 | @tester | ready | Write tests for Bedrock + Vertex parsers (fixtures + round-trip with emitters) |
