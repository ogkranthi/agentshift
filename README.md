# AgentShift

**Convert AI agents between platforms.** Define your agent once, deploy it anywhere.

AgentShift is a CLI transpiler that takes an AI agent definition from one platform and generates deployment-ready configurations for others. No more vendor lock-in for your agents.

```
OpenClaw ──┐
            ├──→ IR ──→ Microsoft Copilot
Claude Code ┘          → AWS Bedrock
                       → GCP Vertex AI
                       → Claude Code
```

## The Problem

AI agents are locked into their originating platforms. An OpenClaw skill can't run on Microsoft Copilot. A Bedrock Agent can't be moved to Vertex AI. Despite 60-70% of an agent being inherently portable, **no tool exists** that converts agents between platforms.

## How It Works

AgentShift parses your agent into a universal **Intermediate Representation (IR)**, then emits platform-specific configurations:

```bash
# Convert an OpenClaw skill to Microsoft Copilot
agentshift convert --to copilot ./my-skill/

# Convert to all supported targets at once
agentshift convert --to all ./my-skill/

# See what ports cleanly vs. what needs manual work
agentshift diff ./my-skill/ --targets copilot,bedrock,vertex

# Validate generated config against platform schema
agentshift validate ./output/copilot/ --target copilot
```

### Portability Matrix

```
$ agentshift diff ./my-skill/ --targets copilot,bedrock

┌─────────────────┬──────────┬─────────┬─────────┐
│ Component        │ OpenClaw │ Copilot │ Bedrock │
├─────────────────┼──────────┼─────────┼─────────┤
│ Instructions     │ ✅ 100%  │ ✅ 100% │ ✅ 100% │
│ Tool: web_search │ ✅       │ ✅ auto │ ✅ auto │
│ Tool: cron       │ ✅       │ ⚠️ stub │ ⚠️ stub │
│ Knowledge (3)    │ ✅       │ ⚠️ stub │ ⚠️ stub │
│ Telegram channel │ ✅       │ ❌ none │ ❌ none │
├─────────────────┼──────────┼─────────┼─────────┤
│ Portability      │          │ 62%     │ 58%     │
└─────────────────┴──────────┴─────────┴─────────┘
```

## Supported Platforms

| Platform | Parser (read) | Emitter (write) | Status |
|----------|:---:|:---:|--------|
| OpenClaw | ✅ | ✅ | In development |
| Claude Code | ✅ | ✅ | In development |
| Microsoft Copilot | — | ✅ | In development |
| AWS Bedrock | — | ✅ | In development |
| GCP Vertex AI | — | ✅ | In development |
| LangGraph | — | — | Planned |
| CrewAI | — | — | Planned |

## Quick Start

### Install

```bash
pip install agentshift
```

### Convert your first agent

```bash
# Option A: Use an OpenClaw built-in skill
cp -r ~/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/weather ./weather-skill
agentshift convert ./weather-skill --from openclaw --to claude-code --output ./weather-claude

# Option B: Use any skill you have installed
agentshift convert ~/.openclaw/skills/my-skill --from openclaw --to claude-code --output ./my-skill-claude

# See what was generated
cat ./weather-claude/CLAUDE.md
cat ./weather-claude/settings.json
```

### See a real conversion

The [examples/](examples/) directory has 4 real before/after conversions:

| Skill | Why interesting |
|-------|----------------|
| [weather](examples/weather-to-claude-code/) | Simplest case — bash-only, no API key |
| [github](examples/github-to-claude-code/) | Tool-heavy: `gh` CLI across PRs, issues, CI |
| [slack](examples/slack-to-claude-code/) | MCP-based — shows MCP tool → `mcp__slack__*` permission mapping |
| [notion](examples/notion-to-claude-code/) | API-rich with structured knowledge |

Each folder has `input/SKILL.md` (original) and `output/` (converted).

## Installation

```bash
pip install agentshift
```

### From source

```bash
git clone https://github.com/ogkranthi/agentshift.git
cd agentshift
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Contributing

We welcome contributions! The most impactful way to contribute is adding support for a new platform.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and guidelines.

### Adding a New Platform

Each platform needs:
1. A **format spec** documenting the agent definition format
2. A **parser** (read from the platform) and/or **emitter** (write to the platform)
3. **Tests** and a **test fixture** with a real agent definition

Open a [Platform Request](https://github.com/ogkranthi/agentshift/issues/new?template=platform_request.yml) to discuss your approach.

## Architecture

```
Source Agent → Parser → IR (Intermediate Representation) → Emitter → Target Config
```

The **IR** is the core — a universal agent model that captures identity, instructions, tools, knowledge, triggers, channels, and constraints. Adding a new platform = writing one parser and/or one emitter. See `specs/ir-schema.json` for the full schema.

## Project Status

AgentShift is in active development. The nightly build crew (autonomous OpenClaw agents) works on it every night. Track progress in [BACKLOG.md](BACKLOG.md).

## License

[Apache License 2.0](LICENSE)
