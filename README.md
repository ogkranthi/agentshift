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

> **OpenClaw users:** Anthropic is [ending Claude subscription access for third-party tools](https://www.theverge.com/news/643004/anthropic-bans-openclaw-claude-extra-pay) on **April 4th, 2025**. AgentShift converts your OpenClaw agents to Claude Code, Copilot, or any supported platform — with governance preserved. **[Migrate now &rarr;](#migrate-from-openclaw)**

Your OpenClaw skill shouldn't be locked to one platform. **AgentShift converts it to Claude Code, GitHub Copilot, AWS Bedrock, Microsoft 365 Copilot, GCP Vertex AI, and more.**

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
agentshift convert ./my-skill --from openclaw --to all --output ./output
# → output/claude-code/  output/copilot/  output/bedrock/  output/m365/  output/vertex/
```

```bash
# Validate generated output before deploying
agentshift validate ./output/bedrock --target bedrock
```

```
weather-claude/               weather-copilot/
├── CLAUDE.md                 ├── weather.agent.md
└── settings.json             └── README.md
```

## Migrate from OpenClaw

With Anthropic ending Claude subscription access for OpenClaw on April 4th, here's how to move your agents:

```bash
# 1. Install
pip install agentshift

# 2. Convert to Claude Code (recommended — closest to OpenClaw)
agentshift convert ~/.openclaw/skills/my-agent --from openclaw --to claude-code -o ./my-agent-claude/

# 3. Audit governance preservation
agentshift audit ~/.openclaw/skills/my-agent --targets claude-code,copilot

# 4. Convert to ALL platforms at once
agentshift convert ~/.openclaw/skills/my-agent --from openclaw --to all -o ./my-agent-output/
```

**Governance preservation** — AgentShift tracks three layers:
- **L1 (Prompt guardrails):** 100% preserved on all platforms
- **L2 (Tool permissions):** 93% on Claude Code, 37% on Copilot (rest elevated to instructions)
- **L3 (Platform-native):** Elevated to prompt instructions with 93.6% behavioral equivalence

Run `agentshift audit` to see exactly what survives for your specific agent.

## How it works

```
1. Parse  →  SKILL.md · CLAUDE.md · .agent.md · AGENTS.md · bot-meta.xml · bedrock-agent.json
              ↓
2. IR     →  identity · tools · knowledge · triggers · constraints · governance
              ↓
3. Emit   →  Claude Code ✅ | Copilot ✅ | Bedrock ✅ | M365 ✅ | Vertex ✅ | A2A ✅ | LangGraph ✅
```

## Parse cloud agent artifacts

```bash
# Parse Bedrock artifacts → convert to OpenClaw skill
agentshift convert ./bedrock-output/ --from bedrock --to openclaw --output ./my-skill

# Parse Vertex AI artifacts → convert to Claude Code
agentshift convert ./vertex-output/ --from vertex --to claude-code --output ./claude-output

# Parse Copilot .agent.md → convert to Bedrock
agentshift convert ./my-copilot/ --from copilot --to bedrock --output ./bedrock-output

# Diff portability from Bedrock source
agentshift diff ./bedrock-output/ --from bedrock --targets claude-code,copilot

# Governance audit: Vertex → Bedrock round-trip
agentshift audit ./vertex-output/ --from vertex --targets bedrock

# Generate A2A Agent Card for platform interoperability
agentshift convert ~/.openclaw/skills/weather --from openclaw --to a2a --output ./weather-a2a
```

## Full-installation migration

```bash
# Migrate entire OpenClaw install to NemoClaw (any cloud)
agentshift migrate --source ~/.openclaw --to nemoclaw --cloud aws --output ./migration
```

Supports `--cloud aws | gcp | azure | docker | bare-metal`. Migrates all skills, cron jobs, network policies, and generates cloud deploy files.

## New in v0.4.0

```bash
# EU AI Act compliance check
agentshift compliance ./my-agent --from claude-code --framework eu-ai-act

# Machine-readable portability scores
agentshift diff ./my-agent --from openclaw --output-format json

# Local agent registry
agentshift registry register ./my-agent --name "github-assistant" --from openclaw
```

## Using with GitHub Actions

```yaml
# Add to .github/workflows/portability.yml
- uses: ogkranthi/agentshift/.github/actions/portability-report@main
```

Automatically comments portability scores on PRs.

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

## Governance layer

AgentShift v0.3 introduces a three-layer governance model that travels with your agent through
every conversion:

| Layer | Model | Source |
|---|---|---|
| **L1 — Guardrails** | `Guardrail` — prompt-level safety rules | SOUL.md, instruction.txt, Bedrock topics, Vertex instructions |
| **L2 — Tool permissions** | `ToolPermission` — per-tool access control | OpenClaw `tools/*.json` |
| **L3 — Platform annotations** | `PlatformAnnotation` — native filters | `governance/annotations.json`, Bedrock guardrail config |

Governance is preserved and audited during conversion:

```bash
# Audit governance preservation: bedrock → claude-code
agentshift audit ./my-bedrock-agent/ --from bedrock --targets claude-code

# Audit from Vertex AI artifacts
agentshift audit ./vertex-output/ --from vertex --targets bedrock,claude-code
```

## Agent registry

Track your agents and detect configuration drift across environments:

```bash
# Register an agent
agentshift registry register ~/.openclaw/skills/weather

# List all registered agents
agentshift registry list

# Detect drift since last registration
agentshift registry diff weather

# Export registry as JSON
agentshift registry export
```

Registry is stored at `~/.agentshift/registry.json` and works offline.

## Supported platforms

| Platform | Read (parser) | Write (emitter) | Status |
|---|:---:|:---:|---|
| OpenClaw | ✅ | ✅ | Works today |
| Claude Code | ✅ | ✅ | Works today |
| GitHub Copilot | ✅ | ✅ | Works today |
| AWS Bedrock | ✅ | ✅ | Works today |
| GCP Vertex AI | ✅ | ✅ | Works today |
| AGENTS.md | ✅ | — | Works today |
| Salesforce Agentforce | ✅ | — | Works today |
| Microsoft 365 | — | ✅ | Works today |
| Google A2A | — | ✅ | Works today |
| LangGraph | — | ✅ | Works today |
| NVIDIA NemoClaw | — | ✅ | Works today |

## Guides

| Target | Guide | Examples |
|---|---|---|
| Claude Code | [docs/claude-code.md](docs/claude-code.md) | [examples/weather-to-claude-code](examples/weather-to-claude-code/) |
| GitHub Copilot | [docs/copilot.md](docs/copilot.md) | [examples/github-to-copilot](examples/github-to-copilot/) |
| AWS Bedrock | [docs/bedrock.md](docs/bedrock.md) | [examples/github-to-bedrock](examples/github-to-bedrock/) |
| Microsoft 365 | [docs/m365.md](docs/m365.md) | [examples/github-to-m365](examples/github-to-m365/) |
| GCP Vertex AI | [docs/vertex.md](docs/vertex.md) | [examples/github-to-vertex](examples/github-to-vertex/) |
| NVIDIA NemoClaw | [docs/nemoclaw.md](docs/nemoclaw.md) | — |
| Architecture | [docs/architecture.md](docs/architecture.md) | — |
| Migration guide | [docs/migrate.md](docs/migrate.md) | — |
| EU AI Act compliance | [docs/compliance.md](docs/compliance.md) | — |
| AGENTS.md source | [docs/agents-md.md](docs/agents-md.md) | — |

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
