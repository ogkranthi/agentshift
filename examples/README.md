# Examples

Real skill conversions from OpenClaw to Claude Code and GitHub Copilot format. Each example shows the original skill alongside the generated output files.

---

## Claude Code examples

### weather → Claude Code

A simple, tool-light skill using `curl` to hit wttr.in.

**Files**
- `weather-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `weather-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `weather-to-claude-code/output/settings.json` — tool permissions

**What changed:** Instructions passed through intact. Bash tool detected → `Bash(bash:*)` permission emitted.

---

### github → Claude Code

A tool-heavy skill using the `gh` CLI for PRs, issues, and CI runs.

**Files**
- `github-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `github-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `github-to-claude-code/output/settings.json` — tool permissions

---

### slack → Claude Code

An MCP-based skill using the `slack` message tool — no bash, all MCP.

**Files**
- `slack-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `slack-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `slack-to-claude-code/output/settings.json` — tool permissions

**What changed:** MCP `slack` tool detected → `mcp__slack__*` permission emitted instead of bash.

---

### notion → Claude Code

A knowledge-rich skill using the Notion API for pages, databases, and blocks.

**Files**
- `notion-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `notion-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `notion-to-claude-code/output/settings.json` — tool permissions

---

## Copilot examples

### weather → Copilot

**Files**
- `weather-to-copilot/weather.agent.md` — Copilot agent definition
- `weather-to-copilot/README.md` — VS Code installation steps

**What changed:** Instructions preserved. Shell usage → `execute/runInTerminal` tool. Model list added from AgentShift defaults.

---

### github → Copilot

**Files**
- `github-to-copilot/github.agent.md` — Copilot agent definition
- `github-to-copilot/README.md` — VS Code installation steps

---

### slack → Copilot

**Files**
- `slack-to-copilot/slack.agent.md` — Copilot agent definition
- `slack-to-copilot/README.md` — VS Code installation steps

**What changed:** MCP tool noted in body; no native Copilot MCP mapping — requires manual VS Code MCP config.

---

## Try it yourself

```bash
# Convert any installed OpenClaw skill
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to claude-code --output ./out-claude
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to copilot --output ./out-copilot

# See what you got
cat out-claude/CLAUDE.md
cat out-copilot/<name>.agent.md
```
