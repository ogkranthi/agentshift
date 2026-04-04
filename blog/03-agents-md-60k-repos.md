---
title: "60,000+ GitHub Repos Have AGENTS.md — Here's How to Convert Them to Claude Code or Copilot"
published: true
description: "AGENTS.md is the de facto standard for AI agent instructions in repos. AgentShift can now parse it and convert to any platform."
tags: github, claudecode, ai, productivity
cover_image: https://agentshift.sh/og-agentsmd.png
canonical_url: https://agentshift.sh
---

If you've worked with AI coding agents in the last year, you've probably written or encountered an `AGENTS.md` file. It's the convention that emerged organically: put your agent instructions in a markdown file at the repo root, and any AI tool that reads the repo picks them up.

There's no official spec. No schema. Just markdown with sections like "Architecture", "Commands", "Do NOT", and "Code Style." But it works, and it's now in over 60,000 GitHub repos.

The problem: `AGENTS.md` instructions are stranded. They're not formatted for Claude Code's `CLAUDE.md`, GitHub Copilot's `.agent.md`, or AWS Bedrock's instruction field. Every developer maintains separate configs for each tool they use.

AgentShift now parses `AGENTS.md` and converts it to any supported platform.

## What AGENTS.md looks like

Here's a typical one:

```markdown
# My Project

## Architecture
FastAPI backend, PostgreSQL database, React frontend.
Main entry: src/main.py. API routes in src/api/.

## Commands
- Run: uvicorn src.main:app --reload
- Test: pytest tests/ -v
- Lint: ruff check src/

## Code Style
- Use type hints on all functions
- Prefer dataclasses over raw dicts
- Keep functions under 50 lines
- No print() — use logging

## Do NOT
- Modify migrations directly — use alembic
- Import from src.legacy
- Commit secrets or API keys
```

No YAML frontmatter. Just markdown. And AgentShift knows how to read it.

## Converting to Claude Code

```bash
agentshift convert . --from agents-md --to claude-code --output ./claude-output
```

What it extracts:

- **Architecture section** → goes into the system prompt as context
- **Commands section** → extracted as tool entries (`uvicorn`, `pytest`, `ruff` become `Bash(uvicorn:*)`, `Bash(pytest:*)`, `Bash(ruff:*)`)
- **Code Style section** → appended to system prompt as style guidelines
- **Do NOT section** → becomes `constraints.guardrails` and appears in a `## Guardrails` section in `CLAUDE.md`

Output `settings.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(uvicorn:*)",
      "Bash(pytest:*)",
      "Bash(ruff:*)"
    ]
  }
}
```

The binary names are extracted from the command bullets — `uvicorn src.main:app --reload` → binary is `uvicorn`.

## Converting to GitHub Copilot

```bash
agentshift convert . --from agents-md --to copilot --output ./copilot-output
```

Generates `my-project.agent.md`:
```yaml
---
name: "my-project"
description: "FastAPI backend, PostgreSQL database, React frontend."
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - execute/runInTerminal
---

# My Project

## Architecture
FastAPI backend, PostgreSQL database, React frontend.
...
```

## See portability before converting

```bash
agentshift diff . --from agents-md

  my-project — Portability Report

  Component         Source   claude-code   copilot   bedrock
  ──────────────────────────────────────────────────────────
  Instructions        ✅      ✅ 100%      ✅ 100%   ✅ 100%
  Tools (shell: 3)    ✅      ✅ Bash(*)   ✅ term   ❌ dropped
  Constraints         ✅      ✅           ⚠️ stub   ⚠️ stub
  ──────────────────────────────────────────────────────────
  Portability                  100%         92%       42%
```

## The pattern across repos

After testing against dozens of AGENTS.md files from public repos, the patterns are consistent:

| Section heading | Maps to |
|---|---|
| Architecture, Overview, Project | System prompt context |
| Commands, Scripts, Run, Build | Shell tools (binary extraction) |
| Code Style, Conventions, Standards | System prompt style section |
| Do NOT, Don't, Never, Avoid | Guardrails list |
| Testing, Tests | Test command tools |
| Everything else | Appended to system prompt |

## Convert any public repo

Since AGENTS.md is just a file in the repo, you can convert any public project:

```bash
git clone https://github.com/some/project
cd project
agentshift convert . --from agents-md --to claude-code --output ./claude
```

Or if you just want to check portability without converting:
```bash
agentshift diff . --from agents-md
```

## Why this matters

The developer community created `AGENTS.md` as a lowest-common-denominator format — readable by any AI tool, writable by any developer. But it's a dead end for deployment: you still need platform-specific configs for Claude Code, Copilot, Bedrock.

AgentShift makes `AGENTS.md` the source of truth. Write once, convert to wherever you're deploying.

```bash
pip install agentshift
agentshift convert . --from agents-md --to all
```

GitHub: [github.com/ogkranthi/agentshift](https://github.com/ogkranthi/agentshift)
