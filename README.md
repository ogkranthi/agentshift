<h1 align="center">AgentShift</h1>
<p align="center"><em>Convert AI agents between platforms. Define once, run anywhere.</em></p>

<p align="center">
  <a href="https://agentshift.sh"><img src="https://img.shields.io/badge/website-agentshift.sh-blue" alt="Website"></a>
  <a href="https://github.com/ogkranthi/agentshift/actions"><img src="https://github.com/ogkranthi/agentshift/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/agentshift/"><img src="https://img.shields.io/pypi/v/agentshift" alt="PyPI version"></a>
  <a href="https://pypi.org/project/agentshift/"><img src="https://img.shields.io/pypi/pyversions/agentshift" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
</p>

---

Your OpenClaw skill shouldn't be locked to one platform. **AgentShift converts it to Claude Code, GitHub Copilot, AWS Bedrock, and more.**

## Install

```bash
# pip
pip install agentshift

# from source
git clone https://github.com/ogkranthi/agentshift.git
cd agentshift && pip install -e .
```

## Quick start

```bash
# → Claude Code
agentshift convert ~/.openclaw/skills/weather --from openclaw --to claude-code --output ./weather-claude

# → GitHub Copilot
agentshift convert ~/.openclaw/skills/weather --from openclaw --to copilot --output ./weather-copilot

# → AWS Bedrock
agentshift convert ~/.openclaw/skills/weather --from openclaw --to bedrock --output ./weather-bedrock

# Convert to ALL supported targets at once
agentshift convert ~/.openclaw/skills/weather --from openclaw --to all --output ./weather-all
# → weather-all/claude-code/  weather-all/copilot/  weather-all/bedrock/
```

```
weather-claude/               weather-copilot/
├── CLAUDE.md                 ├── weather.agent.md
└── settings.json             └── README.md
```

## How it works

```
  Parser  →  SKILL.md · CLAUDE.md · manifest.json · jobs.json
              ↓
  IR      →  identity · tools · knowledge · triggers · constraints
              ↓
  Emitter →  Claude Code ✅  |  Copilot ✅  |  Bedrock ✅  |  Vertex AI 🔜
```

## See portability before converting

```bash
agentshift diff ~/.openclaw/skills/github --from openclaw
```

```
Component          Source    claude-code      copilot        bedrock
─────────────────────────────────────────────────────────────────────
Instructions         ✅       ✅ 100%         ✅ 100%      ✅ 100%
Tools (shell: 2)     ✅    ✅ Bash(bin:*)   ✅ terminal   ⚠️  Lambda*
─────────────────────────────────────────────────────────────────────
Portability                    100%             92%           38%
```

## Supported platforms

| Platform | Read (parser) | Write (emitter) | Status |
|---|:---:|:---:|---|
| OpenClaw | ✅ | ✅ | **Works today** |
| Claude Code | ✅ | ✅ | **Works today** |
| GitHub Copilot | — | ✅ | **Works today** |
| AWS Bedrock | — | ✅ | **Works today** |
| GCP Vertex AI | — | — | Coming soon |
| LangGraph | — | — | Planned |
| CrewAI | — | — | Planned |

## Guides

| Target | Guide | Examples |
|---|---|---|
| Claude Code | [docs/claude-code.md](docs/claude-code.md) | [examples/weather-to-claude-code](examples/weather-to-claude-code/) |
| GitHub Copilot | [docs/copilot.md](docs/copilot.md) | [examples/github-to-copilot](examples/github-to-copilot/) |
| **AWS Bedrock** | **[docs/bedrock.md](docs/bedrock.md)** | **[examples/github-to-bedrock](examples/github-to-bedrock/)** |
| Architecture | [docs/architecture.md](docs/architecture.md) | — |

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
