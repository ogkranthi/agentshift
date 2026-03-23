# Claude Code Agent Format Spec

**Status:** Canonical
**Source:** Observed from `~/.claude/settings.json`, live Claude Code installation, and OpenClaw skill-creator SKILL.md spec.

---

## Overview

Claude Code represents agents through a combination of files:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project context and conventions — injected into every session |
| `~/.claude/settings.json` | Global permissions, allowed tools, additional directories |
| `~/.claude/settings.local.json` | Local overrides (not committed to git) |
| `SKILL.md` | Skill definition (same format as OpenClaw, used by Claude Code skill system) |

---

## CLAUDE.md

### Purpose

`CLAUDE.md` is a free-form Markdown file that Claude Code reads at session start. It provides project-level context and conventions. It is **not** a system prompt override — it supplements Claude's built-in behavior.

Claude Code looks for `CLAUDE.md` files in:
1. The current working directory
2. Parent directories (up to the repo root)
3. `~/.claude/CLAUDE.md` (global, always loaded)

Multiple `CLAUDE.md` files are merged. More-specific files (deeper in the directory tree) take precedence.

### Format

Pure Markdown. No frontmatter. No required sections.

```markdown
# Project Name

Short description of what this project is.

## Tech Stack
- **Language**: TypeScript
- **Framework**: React + Vite
- **Backend**: Vercel serverless functions

## Project Structure
- `src/` — React frontend
- `api/` — Vercel serverless functions
- `scripts/` — Build and automation scripts

## Commands
- `npm run dev` — Start dev server
- `npm run build` — Production build
- `npm test` — Run tests

## Key Design Decisions
- `verbatimModuleSyntax` is enabled — always use `import type` for type-only imports
- All styles in `src/App.css` using CSS custom properties
```

### Observed Conventions

| Section | Description |
|---------|-------------|
| `## Tech Stack` | Languages, frameworks, key packages |
| `## Project Structure` | Directory layout with one-line descriptions |
| `## Commands` | Essential CLI commands for the project |
| `## Key Design Decisions` | Non-obvious conventions Claude must respect |
| `## Architecture` | High-level system design |
| `## API` | Endpoint listing if relevant |
| `## Testing` | Test strategy and commands |

There is no enforced schema. Claude Code reads the full content as context.

### Global CLAUDE.md (`~/.claude/CLAUDE.md`)

Loaded in every session regardless of working directory. Use for:
- Personal preferences that apply to all projects
- Default tools and behaviors
- Cross-project conventions

---

## settings.json Schema

Located at `~/.claude/settings.json`. Controls global Claude Code behavior.

### Top-Level Structure

```json
{
  "permissions": { ... },
  "additionalDirectories": [ ... ],
  "model": "claude-opus-4-5",
  "theme": "dark"
}
```

### `permissions` Object

The permissions object controls which tools Claude Code can use and under what conditions.

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run build)",
      "Bash(git commit:*)",
      "Bash(gh pr:*)",
      "WebSearch",
      "WebFetch(domain:docs.anthropic.com)",
      "Read(/Users/alice/**)"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(git push --force:*)"
    ]
  }
}
```

#### Permission Rule Syntax

Rules follow the pattern `ToolName(argument_pattern)`:

| Pattern | Example | Meaning |
|---------|---------|---------|
| `ToolName` | `WebSearch` | Allow/deny this tool for all inputs |
| `ToolName(literal)` | `Bash(npm run build)` | Exact command match |
| `ToolName(prefix:*)` | `Bash(git commit:*)` | Any command starting with `git commit` |
| `ToolName(domain:host)` | `WebFetch(domain:github.com)` | Specific domain for WebFetch |
| `Read(path/**)`| `Read(/Users/alice/**)` | Path glob for Read tool |

#### Built-in Tools Available in Claude Code

| Tool | Description |
|------|-------------|
| `Bash` | Run shell commands |
| `Read` | Read file contents |
| `Write` | Write/overwrite files |
| `Edit` | Targeted string replacement in files |
| `Glob` | File pattern matching |
| `Grep` | Content search (ripgrep-based) |
| `WebSearch` | Web search |
| `WebFetch` | Fetch a URL |
| `TodoWrite` | Manage task lists |
| `Agent` | Spawn subagents |
| `NotebookEdit` | Edit Jupyter notebooks |

### `additionalDirectories`

Directories outside the working directory that Claude Code can read:

```json
{
  "additionalDirectories": [
    "/Users/alice/.openclaw",
    "/tmp",
    "/private/tmp",
    "/Users/alice/shared-libs"
  ]
}
```

### `settings.local.json`

Same schema as `settings.json`. Loaded after `settings.json` and merged. Intended for machine-local overrides not committed to source control.

---

## SKILL.md in Claude Code

Claude Code uses the same `SKILL.md` format as OpenClaw for its skill system. The format is identical — see `specs/openclaw-skill-format.md` for the full spec.

### YAML Frontmatter

```yaml
---
name: my-skill
description: "What this skill does. Use when: ... NOT for: ..."
---
```

Only `name` and `description` are supported in Claude Code SKILL.md frontmatter. The `metadata.openclaw` extensions (`emoji`, `requires`, `install`) are OpenClaw-specific and ignored by Claude Code.

### Body

Full Markdown instructions. Same progressive disclosure pattern as OpenClaw skills — the body is loaded only after the skill triggers.

### Skill Directory

Claude Code skills live in `~/.claude/skills/<skill-name>/SKILL.md` or alongside the project.

The supporting files (`AGENTS.md`, `SOUL.md`, `USER.md`, etc.) are OpenClaw conventions and are not part of the Claude Code skill system directly. However, Claude Code will read them if referenced in `CLAUDE.md` or `SKILL.md`.

---

## Expressing Agent Capabilities in Claude Code

### Tools / Capabilities

Tools are expressed through `settings.json` permissions (which tools are allowed) and `CLAUDE.md`/`SKILL.md` instructions (how to use them):

**settings.json** — grant access:
```json
{
  "permissions": {
    "allow": [
      "Bash(gh:*)",
      "WebFetch(domain:api.github.com)"
    ]
  }
}
```

**SKILL.md body** — instruct usage:
```markdown
## GitHub Operations

Use the `gh` CLI for all GitHub interactions:

```bash
gh pr list --repo owner/repo
gh issue create --title "Bug" --body "Details"
```
```

### Knowledge Sources

Referenced by path in `CLAUDE.md` or `SKILL.md`. The agent uses the `Read` tool to load them:

```markdown
## Reference Files

- `docs/api-schema.json` — Full API schema
- `docs/conventions.md` — Coding conventions
```

### Triggers (Cron)

Claude Code has no built-in cron scheduler. Triggers are implemented externally:

1. **System cron** + `claude --print` CLI:
   ```cron
   0 9 * * * cd /path/to/project && claude --print --permission-mode bypassPermissions "Run the daily report"
   ```

2. **OpenClaw cron** targeting a Claude Code session (via `coding-agent` skill):
   ```json
   {
     "payload": {
       "kind": "agentTurn",
       "message": "cd ~/project && claude --permission-mode bypassPermissions --print 'Check for new issues and triage them'"
     }
   }
   ```

3. **GitHub Actions** / CI scheduling for project-level automation.

---

## Project-Level `.claude/` Directory

A project can include a `.claude/` directory for project-scoped configuration:

```
project/
└── .claude/
    ├── settings.json    # Project-scoped permissions (committed to git)
    └── settings.local.json  # Local overrides (gitignored)
```

Project-level `settings.json` is merged with the global `~/.claude/settings.json`. Project settings take precedence.

---

## Skill Triggering

Claude Code routes to skills based on the `description` field in `SKILL.md` frontmatter. The routing is semantic — Claude reads the description and decides whether to load the skill body.

Best practice (same as OpenClaw):

```yaml
description: "GitHub operations via `gh` CLI. Use when: (1) checking PR status, (2) creating issues, (3) viewing CI runs. NOT for: local git operations, non-GitHub repos."
```

---

## Complete Example — Single-File Agent

A minimal Claude Code agent is just a `CLAUDE.md`:

```markdown
# My Project Agent

This agent helps with Python data analysis projects.

## Tech Stack
- Python 3.11+
- pandas, numpy, matplotlib
- Jupyter notebooks in `notebooks/`

## Conventions
- All data files in `data/raw/` (never modify these)
- Processed data in `data/processed/`
- Outputs in `outputs/`

## Commands
- `pytest tests/` — Run tests
- `jupyter lab` — Start notebook server
- `python scripts/process_data.py` — Run pipeline

## Key Rules
- Never write to `data/raw/` — read only
- Always document new functions with docstrings
- Run tests before committing
```

With `settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(pytest:*)",
      "Bash(python:*)",
      "Bash(jupyter:*)",
      "WebSearch"
    ]
  },
  "additionalDirectories": ["/Users/alice/datasets"]
}
```

---

## Complete Example — Skill-Based Agent

A more structured agent with `SKILL.md`:

**`~/.claude/skills/github-reviewer/SKILL.md`:**

```yaml
---
name: github-reviewer
description: "Automated GitHub PR review agent. Use when: reviewing pull requests, checking CI status, creating review comments. NOT for: local git operations, non-GitHub work."
---

# GitHub PR Reviewer

## Workflow

1. List open PRs: `gh pr list --repo owner/repo --state open`
2. Review changed files: `gh pr diff <number>`
3. Check CI: `gh pr checks <number>`
4. Post review: `gh pr review <number> --comment -b "Review notes"`

## Review Checklist

- Tests added or updated?
- No obvious security issues (SQL injection, XSS, secrets in code)?
- PR description is clear?
- Breaking changes documented?

## Commands

```bash
# Full PR review context
gh pr view <number> --json title,body,author,additions,deletions,changedFiles

# Post approval
gh pr review <number> --approve

# Request changes
gh pr review <number> --request-changes -b "Please address the issues above"
```
```

---

## Mapping: Claude Code vs OpenClaw

| Concept | Claude Code | OpenClaw |
|---------|-------------|----------|
| Agent instructions | `CLAUDE.md` + `SKILL.md` body | `SKILL.md` body |
| Skill trigger | `description` in `SKILL.md` | `description` in `SKILL.md` |
| Tool permissions | `settings.json` `permissions.allow` | `metadata.openclaw.requires` |
| Knowledge files | `Read` tool + paths in `CLAUDE.md` | `knowledge/` dir + paths in SKILL.md |
| Cron triggers | External (system cron, GH Actions) | `~/.openclaw/cron/jobs.json` |
| Agent identity | `CLAUDE.md` prose | `SOUL.md` + `IDENTITY.md` |
| User profile | `CLAUDE.md` or `~/.claude/CLAUDE.md` | `USER.md` |
| Heartbeat | Not natively supported | `HEARTBEAT.md` + cron job |
| Install steps | Not expressed | `metadata.openclaw.install` |
| Multi-file workspace | `additionalDirectories` | `~/.openclaw/skills/<name>/` |
| Emoji | Not natively supported | `metadata.openclaw.emoji` |
