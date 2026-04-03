# AGENTS.md → IR Parser Spec

**Spec ID:** A20
**Status:** Canonical
**Author:** @architect

---

## 1. Overview

AGENTS.md is a community convention used in **60,000+ GitHub repositories** where developers write
instructions for AI coding agents. Unlike platform-specific formats (CLAUDE.md, .agent.md, Bedrock
agent.json), AGENTS.md is platform-agnostic — it's pure markdown with no YAML frontmatter.

The AgentShift `agents-md` parser converts these files into IR, making 60k+ repos instantly
portable to Claude Code, GitHub Copilot, Bedrock, Vertex AI, and other targets.

**Input artifacts:**

| File | Role | Required? |
|------|------|-----------|
| `AGENTS.md` | Agent instructions (pure markdown) | Required |

---

## 2. Section Conventions

AGENTS.md files typically use H2 (`##`) sections. Common conventions:

| Section Heading | Content | IR Mapping |
|-----------------|---------|------------|
| Architecture / Overview / Project | System design, entry points, directory layout | `persona.system_prompt` (prepended) |
| Commands / Scripts / Run / Build / Test | Shell commands as bullets or code blocks | `tools[]` (kind=shell) |
| Code Style / Conventions / Formatting | Coding standards and preferences | `persona.system_prompt` (appended as style) |
| Do NOT / Don't / Never / Avoid | Prohibited actions and anti-patterns | `governance.guardrails` + `constraints.guardrails` |
| Testing / Tests | Test commands and conventions | `tools[]` (kind=shell) |
| Everything else | General instructions | `persona.system_prompt` (appended) |

### 2.1 Name Extraction

- **H1 heading** (`# Project Name`) → slugified as `ir.name`
- **Fallback:** directory name containing the AGENTS.md file

### 2.2 Description Extraction

- First non-heading paragraph after the H1 → `ir.description`
- **Fallback:** `"Agent instructions from AGENTS.md"`

### 2.3 Tool Extraction

Commands are extracted from two patterns:

**Bullet points:**
```markdown
- Run server: `uvicorn src.main:app --reload`
- Test: `pytest tests/ -v`
```
→ `Tool(name="uvicorn", description="Run server: uvicorn src.main:app --reload", kind="shell")`

**Code blocks:**
````markdown
```bash
npm install
npm start
```
````
→ `Tool(name="npm", description="Run: npm install", kind="shell")` (one per line)

### 2.4 Guardrail Extraction

Each bullet in a "Do NOT" section becomes a `Guardrail`:
```markdown
## Do NOT
- Modify migrations directly — use alembic
```
→ `Guardrail(id="agents-md-rule-1", text="Modify migrations directly — use alembic", category="operational")`

---

## 3. IR Mapping Reference

| IR Field | Source | Notes |
|----------|--------|-------|
| `name` | H1 heading (slugified) | Falls back to directory name |
| `description` | First paragraph | Falls back to generic text |
| `persona.system_prompt` | Architecture + Style + other sections | Concatenated with `\n\n` |
| `tools[]` | Commands/Scripts/Test sections | kind=shell, binary extracted |
| `governance.guardrails` | Do NOT / Never / Avoid sections | category=operational |
| `constraints.guardrails` | Guardrail ID references | Links to governance entries |
| `metadata.source_platform` | — | Always `"agents-md"` |
| `metadata.source_file` | — | Path to parsed AGENTS.md |

---

## 4. Limitations

AGENTS.md is instructions-only. The following IR features have **no source data**:

| IR Feature | Status | Reason |
|------------|--------|--------|
| `tools[].auth` | Not available | No auth conventions in AGENTS.md |
| `triggers[]` | Not available | No scheduling/event conventions |
| `knowledge[]` | Not available | No file attachment conventions |
| `install[]` | Not available | No dependency install conventions |
| `governance.tool_permissions` | Not available | No per-tool access control |
| `governance.platform_annotations` | Not available | No platform-native governance |

These can be manually added to the IR after parsing, or supplemented by other config files.

---

## 5. CLI Usage

```bash
# Convert AGENTS.md to Claude Code format
agentshift convert ./my-repo --from agents-md --to claude-code

# Convert to all supported targets
agentshift convert ./my-repo --from agents-md --to all

# Show portability matrix
agentshift diff ./my-repo --from agents-md
```
