# Examples

Real skill conversions from OpenClaw to Claude Code format. Each example shows the original `SKILL.md` alongside the generated `CLAUDE.md` + `settings.json`.

---

## weather → Claude Code

A simple, tool-light skill using `curl` to hit wttr.in. Good starting point.

**Files**
- `weather-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `weather-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `weather-to-claude-code/output/settings.json` — Claude Code permissions

**What changed:** Instructions passed through intact. Tool detection picked up `bash` → emitted `Bash(bash:*)` permission.

---

## github → Claude Code

A tool-heavy skill using the `gh` CLI for PRs, issues, and CI runs.

**Files**
- `github-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `github-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `github-to-claude-code/output/settings.json` — Claude Code permissions

**What changed:** `gh` CLI usage detected as bash tool → `Bash(bash:*)` permission emitted.

---

## slack → Claude Code

An MCP-based skill using the `slack` message tool — no bash, all MCP.

**Files**
- `slack-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `slack-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `slack-to-claude-code/output/settings.json` — Claude Code permissions

**What changed:** MCP `slack` tool detected → `mcp__slack__*` permission emitted instead of bash. Shows how tool type affects the output.

---

## notion → Claude Code

A knowledge-rich skill using the Notion API for pages, databases, and blocks.

**Files**
- `notion-to-claude-code/input/SKILL.md` — original OpenClaw skill
- `notion-to-claude-code/output/CLAUDE.md` — converted agent instructions
- `notion-to-claude-code/output/settings.json` — Claude Code permissions

**What changed:** API-heavy instructions passed through. Bash tool detected for curl-based API calls.

---

## Try it yourself

**Step 1: Get a skill** (pick one of these)

Option A — Use an installed OpenClaw skill:
```bash
ls ~/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/
```

Option B — Copy this example:
```bash
cp -r examples/weather-to-claude-code/input my-skill
```

Option C — Pull from ClaWHub (when available):
```bash
openclaw skill install <skill-name>
cp -r ~/.openclaw/skills/<skill-name> my-skill
```

**Step 2: Convert it**
```bash
agentshift convert my-skill --from openclaw --to claude-code --output my-skill-claude
```

**Step 3: See what changed**
```bash
diff examples/weather-to-claude-code/input/SKILL.md my-skill-claude/CLAUDE.md
cat my-skill-claude/CLAUDE.md
cat my-skill-claude/settings.json
```
