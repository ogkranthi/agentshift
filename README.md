<h1 align="center">AgentShift</h1>
<p align="center"><em>Convert AI agents between platforms. Define once, run anywhere.</em></p>

<p align="center">
  <img src="docs/demo-placeholder.svg" alt="AgentShift demo" width="700">
</p>

<p align="center">
  <a href="https://github.com/ogkranthi/agentshift/actions"><img src="https://github.com/ogkranthi/agentshift/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/agentshift/"><img src="https://img.shields.io/pypi/v/agentshift" alt="PyPI version"></a>
  <a href="https://pypi.org/project/agentshift/"><img src="https://img.shields.io/pypi/pyversions/agentshift" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
</p>

---

Your OpenClaw skill, your Bedrock Agent, your Copilot — they all speak different dialects.
**AgentShift is the translator.**

## Install

```bash
# pip
pip install agentshift

# from source
git clone https://github.com/ogkranthi/agentshift.git
cd agentshift && pip install -e .
```

## Usage

```bash
# Copy a built-in OpenClaw skill and convert it to Claude Code
cp -r ~/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/weather ./weather-skill
agentshift convert ./weather-skill --from openclaw --to claude-code --output ./weather-claude

# Convert any skill you have installed
agentshift convert ~/.openclaw/skills/my-skill --from openclaw --to claude-code --output ./my-skill-claude

# Inspect the output
cat ./weather-claude/CLAUDE.md
cat ./weather-claude/settings.json
```

## How it works

AgentShift parses your agent into a universal **Intermediate Representation (IR)**, then emits platform-specific configs.

```
  1. Parse  →  SKILL.md · CLAUDE.md · manifest.json · instruction.txt
               ↓
  2. IR     →  identity · tools · knowledge · triggers · constraints
               ↓
  3. Emit   →  Claude Code  ✅  |  Copilot  🔜  |  Bedrock  🔜  |  Vertex AI  🔜
```

The IR is the core abstraction — captured in `specs/ir-schema.json`. Adding a new platform means writing one parser and/or one emitter. Nothing else changes.

## Supported platforms

| Platform | Read (parser) | Write (emitter) | Status |
|---|:---:|:---:|---|
| OpenClaw | ✅ | ✅ | **Works today** |
| Claude Code | ✅ | ✅ | **Works today** |
| Microsoft Copilot | — | — | Coming soon |
| AWS Bedrock | — | — | Coming soon |
| GCP Vertex AI | — | — | Coming soon |
| LangGraph | — | — | Planned |
| CrewAI | — | — | Planned |

## See a real conversion

The [`examples/`](examples/) directory has 4 complete before/after conversions.

**Input** — `examples/weather-to-claude-code/input/SKILL.md` (OpenClaw):

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
curl "wttr.in/London"               # 3-day forecast
curl "wttr.in/London?format=j1"     # JSON output
```
```

**Output** — `examples/weather-to-claude-code/output/CLAUDE.md` (Claude Code):

```markdown
# weather

Get current weather and forecasts via wttr.in. No API key needed.

## Instructions
...

## Tools
- **bash** (shell): Run shell commands
```

**Output** — `examples/weather-to-claude-code/output/settings.json`:

```json
{ "permissions": { "allow": ["Bash(bash:*)"] } }
```

More examples: [github](examples/github-to-claude-code/) · [slack](examples/slack-to-claude-code/) · [notion](examples/notion-to-claude-code/)

## Contributing

Contributions welcome — especially new platform parsers/emitters.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, architecture, and PR guidelines.

```bash
git clone https://github.com/ogkranthi/agentshift.git
cd agentshift
pip install -e ".[dev]"
agentshift --help
```

Open a [Platform Request](https://github.com/ogkranthi/agentshift/issues/new?template=platform_request.yml) to discuss adding a new target.

## License

[Apache License 2.0](LICENSE)
