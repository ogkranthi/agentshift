<h1 align="center">AgentShift</h1>
<p align="center"><em>Convert AI agents between platforms. Define once, run anywhere.</em></p>

<p align="center">
  <a href="https://github.com/ogkranthi/agentshift/actions"><img src="https://github.com/ogkranthi/agentshift/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/agentshift/"><img src="https://img.shields.io/pypi/v/agentshift" alt="PyPI version"></a>
  <a href="https://pypi.org/project/agentshift/"><img src="https://img.shields.io/pypi/pyversions/agentshift" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
</p>

---

Your OpenClaw skill shouldn't be locked to one platform. **AgentShift converts it to Claude Code, GitHub Copilot, and more.**

## Install

```bash
# pip
pip install agentshift

# from source
git clone https://github.com/ogkranthi/agentshift.git
cd agentshift && pip install -e .
```

## Convert your first agent

Same skill, two targets — pick the one you want:

```bash
# → Claude Code
agentshift convert ~/.openclaw/skills/weather --from openclaw --to claude-code --output ./weather-claude

# → GitHub Copilot
agentshift convert ~/.openclaw/skills/weather --from openclaw --to copilot --output ./weather-copilot
```

```
weather-claude/               weather-copilot/
├── CLAUDE.md                 ├── weather.agent.md
└── settings.json             └── README.md
```

## How it works

```
  1. Parse  →  SKILL.md · CLAUDE.md · manifest.json · instruction.txt
               ↓
  2. IR     →  identity · tools · knowledge · triggers · constraints
               ↓
  3. Emit   →  Claude Code ✅  |  Copilot ✅  |  Bedrock 🔜  |  Vertex AI 🔜
```

The IR is the core abstraction — captured in `specs/ir-schema.json`. Adding a new platform means writing one parser and/or one emitter. Nothing else changes.

## Supported platforms

| Platform | Read (parser) | Write (emitter) | Status |
|---|:---:|:---:|---|
| OpenClaw | ✅ | ✅ | **Works today** |
| Claude Code | ✅ | ✅ | **Works today** |
| GitHub Copilot | — | ✅ | **Works today** |
| AWS Bedrock | — | — | Coming soon |
| GCP Vertex AI | — | — | Coming soon |
| LangGraph | — | — | Planned |
| CrewAI | — | — | Planned |

---

## Using with Claude Code

### Step 1: Convert

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to claude-code --output ./github-claude
```

Produces:
```
github-claude/
├── CLAUDE.md       ← instructions + persona (Claude Code reads this automatically)
└── settings.json   ← tool permissions (Bash, MCP, Read/Write paths)
```

### Step 2: Place the files

| Location | Scope | When to use |
|---|---|---|
| `~/.claude/CLAUDE.md` | Global — all projects | Skills you want everywhere |
| `<project>/.claude/CLAUDE.md` | Project-only | Skills scoped to one repo |

```bash
# Option A — global
mkdir -p ~/.claude
cp github-claude/CLAUDE.md ~/.claude/CLAUDE.md
cp github-claude/settings.json ~/.claude/settings.json

# Option B — project-scoped
mkdir -p my-project/.claude
cp github-claude/CLAUDE.md my-project/.claude/CLAUDE.md
cp github-claude/settings.json my-project/.claude/settings.json
```

> **Multiple skills:** Claude Code loads one `CLAUDE.md` per scope. Concatenate files and merge permission arrays to combine — or wait for `agentshift merge` (coming soon).

### Step 3: Use it

```bash
cd my-project
claude   # or claude --print "check open PRs"
```

### Step 4: Verify tool permissions

```bash
cat github-claude/settings.json
# → { "permissions": { "allow": ["Bash(bash:*)"] } }
```

---

### What carries over from OpenClaw

| OpenClaw feature | Claude Code equivalent | Status |
|---|---|---|
| Skill instructions (body) | `CLAUDE.md` — loaded automatically | ✅ Full fidelity |
| Shell tool permissions | `settings.json` `allow: ["Bash(<binary>:*)"]` | ✅ Precise per-binary |
| MCP tools (slack, github) | `settings.json` `allow: ["mcp__<name>__*"]` | ✅ Works if MCP server configured |
| Knowledge files | `CLAUDE.md` knowledge section + `Read(path)` permissions | ✅ Paths preserved |
| Data file writes | `Write(path)` in `settings.json` | ✅ Exact paths |
| OS constraints | `settings.json` `supportedOs` | ✅ Preserved |
| Cron / scheduled triggers | Cloud Scheduled Tasks (Anthropic-managed) | ✅ See below |
| Install dependencies | Not applicable — assumes tools installed | ⚠️ Manual step |
| Telegram / Slack delivery | Not supported natively | ⚠️ See below |

---

### Scheduled triggers

Claude Code has **cloud-managed scheduled tasks** that keep running even when your computer is off — just like OpenClaw cron jobs.

```bash
# Option 1 — conversational
/schedule daily PR review at 9am

# Option 2 — in-session loop
/loop 30m check if the deployment finished

# Option 3 — web UI: https://claude.ai/code/scheduled → New scheduled task
```

| OpenClaw (`jobs.json`) | Claude Code |
|---|---|
| `"schedule": "0 9 * * *"` | `/schedule daily at 9am` or set via web UI |
| `"message": "Give today's tip"` | Prompt field in the scheduled task |
| `"session_target": "isolated"` | Each run is a fresh cloud session (default) |

> `/loop` tasks disappear when Claude Code exits. For durable cron, use [cloud scheduled tasks](https://claude.ai/code/scheduled).

---

### Remaining gaps

**1. Proactive delivery (Telegram, Slack, Discord)**
OpenClaw pushes results to messaging channels. Claude Code scheduled tasks output to GitHub branches or logs.

*Workaround:* End your scheduled task prompt with:
```
... do the work, then write the summary to summary.md and commit it to daily-summary/YYYY-MM-DD
```

**2. Persistent memory across sessions**
OpenClaw persists `MEMORY.md`. Claude Code sessions are stateless by default.

*Workaround:* Reference memory files in your project-level `CLAUDE.md` or pass them in your scheduled task prompt.

**3. Multi-channel routing**
OpenClaw routes output to Telegram, Slack, Discord, or email. Claude Code outputs to stdout or GitHub only.

---

## Using with GitHub Copilot

### Step 1: Convert

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to copilot --output ./github-copilot
```

Produces:
```
github-copilot/
├── github.agent.md   ← Copilot agent definition (frontmatter + instructions)
└── README.md         ← installation steps for VS Code
```

The generated `github.agent.md` looks like:

```yaml
---
name: "github"
description: "GitHub operations via gh CLI..."
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "Claude Opus 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - execute/runInTerminal
---

# GitHub Skill
... instructions ...
```

### Step 2: Install in VS Code

**Option A — Command palette (personal use):**
1. Open VS Code
2. `Cmd+Shift+P` → "GitHub Copilot: Install Agent from File"
3. Select `github.agent.md`
4. Agent appears as `@github` in Copilot Chat

**Option B — Workspace (share with team):**
```bash
mkdir -p .github/copilot-agents
cp github-copilot/github.agent.md .github/copilot-agents/
```
Commit to repo — all team members get the agent automatically.

### Step 3: Use it

In VS Code Copilot Chat:
```
@github list open PRs for owner/repo
@github check CI status on PR #55
```

### Step 4: Verify

```bash
cat github-copilot/github.agent.md | head -10
# → tools: [execute/runInTerminal]
```

---

### What carries over for Copilot

| OpenClaw feature | Copilot equivalent | Status |
|---|---|---|
| Skill instructions (body) | Agent markdown body | ✅ Full fidelity |
| Shell tool usage | `execute/runInTerminal` | ✅ Maps cleanly |
| Knowledge file reads | `read/readFile` tool | ✅ |
| Data file writes | `edit/editFiles` tool | ✅ |
| MCP tools (slack, notion) | MCP server — configure separately in VS Code | ⚠️ Manual step |
| Cron / scheduled triggers | Not supported — Copilot is chat-only | ❌ |
| Telegram / Slack delivery | Not applicable | ❌ |

---

### Contribute to awesome-copilot

The generated `.agent.md` files can be submitted directly to [github/awesome-copilot](https://github.com/github/awesome-copilot):

```bash
# Fork https://github.com/github/awesome-copilot
# Convert your skill
agentshift convert ~/.openclaw/skills/github --from openclaw --to copilot --output /tmp/out
# Add to fork
cp /tmp/out/github.agent.md agents/github-cli.agent.md
# Open PR
gh pr create --repo github/awesome-copilot --title "feat: add github-cli agent (converted from OpenClaw via AgentShift)"
```

---

## See real conversions

| Skill | Claude Code output | Copilot output |
|---|---|---|
| weather | [examples/weather-to-claude-code/](examples/weather-to-claude-code/) | [examples/weather-to-copilot/](examples/weather-to-copilot/) |
| github | [examples/github-to-claude-code/](examples/github-to-claude-code/) | [examples/github-to-copilot/](examples/github-to-copilot/) |
| slack | [examples/slack-to-claude-code/](examples/slack-to-claude-code/) | [examples/slack-to-copilot/](examples/slack-to-copilot/) |
| notion | [examples/notion-to-claude-code/](examples/notion-to-claude-code/) | — |

**Before** — `examples/weather-to-claude-code/input/SKILL.md` (OpenClaw):

```yaml
---
name: weather
description: "Get current weather and forecasts via wttr.in. No API key needed."
metadata: { "openclaw": { "emoji": "☔", "requires": { "bins": ["curl"] } } }
---

# Weather Skill

## Commands

```bash
curl "wttr.in/London?format=3"      # one-line summary
curl "wttr.in/London?format=j1"     # JSON output
```
```

**After (Claude Code)** — `CLAUDE.md` + `settings.json`:

```markdown
# weather

Get current weather and forecasts via wttr.in. No API key needed.

## Instructions
...
```
```json
{ "permissions": { "allow": ["Bash(bash:*)"] } }
```

**After (Copilot)** — `weather.agent.md`:

```yaml
---
name: "weather"
description: "Get current weather and forecasts via wttr.in..."
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "Claude Opus 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - execute/runInTerminal
  - web
  - search
---

# Weather Skill
...
```

## Contributing

Contributions welcome — especially new platform parsers/emitters.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, architecture, and PR guidelines.

```bash
git clone https://github.com/ogkranthi/agentshift.git
cd agentshift && pip install -e ".[dev]"
agentshift --help
```

Open a [Platform Request](https://github.com/ogkranthi/agentshift/issues/new?template=platform_request.yml) to discuss a new target.

## License

[Apache License 2.0](LICENSE)
