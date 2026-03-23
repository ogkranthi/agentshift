# GitHub Copilot Agent Format Spec

## Overview

GitHub Copilot supports two agent formats:

1. **`.agent.md` — Full agents** (this document)
2. **`SKILL.md` — Skills** (identical to OpenClaw SKILL.md format; see `openclaw-skill-format.md`)

This document covers `.agent.md` and how to map AgentShift IR to it.

---

## Format 1: `.agent.md` — Full Agents

### File structure

```
<slug>.agent.md
```

YAML frontmatter followed by a markdown body (the agent instructions).

### Frontmatter fields

```yaml
---
name: "Agent Name"
description: "What the agent does — shown in the Copilot agent picker."
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "Claude Opus 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - execute/runInTerminal
  - read/readFile
  - edit/editFiles
  - web
  - search
---
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | yes | Display name shown in VS Code |
| `description` | string | yes | Short description in agent picker |
| `model` | list[string] | yes | Ordered preference list; first available model is used |
| `tools` | list[string] | yes | Tool IDs the agent may invoke |

### Markdown body

Everything after the closing `---` is the agent's system prompt / instruction set. Plain GitHub Flavored Markdown.

```markdown
# My Agent

You are a helpful assistant that...

## Rules
- Rule one
- Rule two
```

---

## Known Tool IDs

### Execute (shell / terminal)

| Tool ID | What it does |
|---------|-------------|
| `execute/runInTerminal` | Run a command in the integrated terminal |
| `execute/runTask` | Run a VS Code task by name |
| `execute/createAndRunTask` | Create and immediately run a task |
| `execute/getTerminalOutput` | Read output from the last terminal run |

### Read (file / workspace)

| Tool ID | What it does |
|---------|-------------|
| `read/readFile` | Read a file from the workspace |
| `read/problems` | Read compiler/linter diagnostics |
| `read/terminalLastCommand` | Read last terminal command + output |
| `read/getTaskOutput` | Read output from a named task |

### Edit

| Tool ID | What it does |
|---------|-------------|
| `edit/editFiles` | Create, modify, or delete workspace files |

### Web / search

| Tool ID | What it does |
|---------|-------------|
| `web` | Fetch web pages or call HTTP APIs |
| `search` | Search the web via Bing |

### Agentic / meta

| Tool ID | What it does |
|---------|-------------|
| `agent` | Invoke another registered Copilot agent |
| `todo` | Manage VS Code TODO items |

### GitHub (requires `github.vscode-pull-request-github` extension)

| Tool ID | What it does |
|---------|-------------|
| `github.vscode-pull-request-github/doSearch` | Search GitHub issues, PRs, code |
| `github.vscode-pull-request-github/activePullRequest` | Get context of the active PR |

### VS Code integration

| Tool ID | What it does |
|---------|-------------|
| `vscode/runCommand` | Run a VS Code command by ID |
| `vscode/getProjectSetupInfo` | Read project language/framework info |

---

## Known Model IDs

Use these in the `model` list:

| Model ID | Notes |
|----------|-------|
| `Claude Sonnet 4.6 (copilot)` | Recommended default — fast, high quality |
| `Claude Opus 4.6 (copilot)` | Highest capability, slower |
| `Claude Haiku 4.5 (copilot)` | Fastest, lightweight tasks |
| `GPT-5.3-Codex` | OpenAI alternative |
| `o3` | OpenAI reasoning model |

---

## Complete Example

```markdown
---
name: "PR Reviewer"
description: "Reviews open pull requests for code quality and security issues"
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "Claude Opus 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - read/readFile
  - edit/editFiles
  - github.vscode-pull-request-github/activePullRequest
  - github.vscode-pull-request-github/doSearch
---

# PR Reviewer

You are a senior engineer reviewing pull requests for correctness, security, and style.

## Behaviour
- Read the active PR diff using the GitHub PR tool.
- Check for OWASP Top 10 vulnerabilities.
- Flag TODO comments that should be addressed before merge.
- Suggest concise, actionable improvements in the review.
- Do not approve PRs; only provide feedback.
```

---

## Format 2: SKILL.md — Skills

Copilot skills use the same `SKILL.md` format as OpenClaw. See `openclaw-skill-format.md` for the full specification. Skills are lighter-weight than full agents — they add capabilities to the base Copilot assistant rather than replacing its persona.

---

## IR → Copilot Mapping

| IR field | Copilot field | Notes |
|----------|---------------|-------|
| `name` | frontmatter `name` | Direct mapping |
| `description` | frontmatter `description` | Direct mapping |
| `persona.system_prompt` | markdown body | Full system prompt becomes the body |
| `tools[kind=shell]` | `execute/runInTerminal` | All shell tools map to terminal execution |
| `tools[kind=mcp]` | _(comment only)_ | MCP requires server config outside `.agent.md`; emit a comment |
| `tools[kind=builtin]` with web_search / curl | `web` | Web fetch / search capability |
| `knowledge[kind=file\|directory]` | `read/readFile` | File access |
| data writes detected in system_prompt | `edit/editFiles` | Write/edit capability |
| `metadata.model_preference` | `model` list | Merged with default model list |

### MCP tools

MCP servers cannot be declared inside `.agent.md`. When the IR contains `tools[kind=mcp]`, the emitter:

1. Emits a comment block at the top of the markdown body:
   ```
   <!-- MCP: configure <name> server separately in VS Code settings -->
   ```
2. Documents required servers in the output `README.md`.

---

## Contributing to github/awesome-copilot

[github/awesome-copilot](https://github.com/github/awesome-copilot) is the community registry for Copilot agents and skills.

### File naming

Agents submitted to the registry must be named:
```
agents/<slug>.agent.md
```

Where `<slug>` is lowercase with hyphens, matching the `name` field slugified. Example: an agent named "PR Reviewer" → `agents/pr-reviewer.agent.md`.

### Requirements

- `name` and `description` must be present and descriptive.
- At least one tool must be declared.
- The markdown body must contain meaningful instructions (not placeholder text).
- The agent must be scoped — avoid overly broad "do everything" agents.

### Submission steps

1. Fork [github/awesome-copilot](https://github.com/github/awesome-copilot).
2. Place your `.agent.md` file at `agents/<slug>.agent.md`.
3. Add an entry to `agents/README.md` in the table.
4. Open a pull request with title: `Add <slug> agent`.

### AgentShift workflow

```bash
# Convert OpenClaw skill → Copilot .agent.md
agentshift convert ~/.openclaw/skills/my-skill --from openclaw --to copilot --output /tmp/copilot-my-skill

# Review output
cat /tmp/copilot-my-skill/my-skill.agent.md

# Copy to awesome-copilot fork
cp /tmp/copilot-my-skill/my-skill.agent.md path/to/awesome-copilot/agents/
```

---

## Limitations vs. OpenClaw IR

| IR capability | Copilot support | Workaround |
|---------------|----------------|------------|
| Cron triggers | None | Use VS Code task scheduler or external cron + HTTP webhook |
| MCP server config | Not in `.agent.md` | Configure separately in VS Code `settings.json` → `github.copilot.chat.agent.mcp.server` |
| Auth / API keys | Not in `.agent.md` | User must set env vars or VS Code secrets |
| Delivery channels (Telegram, Slack) | None | Not applicable to IDE context |
| Multiple knowledge files | `read/readFile` only | Agent must be instructed to read specific paths |
| Instruction length limit | ~32 000 chars | Well within range for most OpenClaw skills |
