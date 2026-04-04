# NemoClaw Agent Format Specification

## Overview

**NemoClaw** is an open-source reference stack by NVIDIA that runs OpenClaw agents inside hardened OpenShell sandboxes. It is **not** a new agent format — it uses the same workspace files as OpenClaw (SKILL.md, SOUL.md, IDENTITY.md) but wraps them in:

1. A sandboxed Docker/k3s container with Landlock LSM
2. Network policies (deny-by-default egress)
3. Inference routing via NVIDIA OpenShell gateway (Nemotron, NVIDIA Endpoints, or other providers)
4. State management (migration snapshots, credential stripping)

Workspace files live at `/sandbox/.openclaw/workspace/` inside the sandbox.

## Output Structure

```
output/
├── workspace/
│   ├── SKILL.md              ← Agent skill definition (OpenClaw format)
│   ├── SOUL.md               ← Agent persona and boundaries
│   └── IDENTITY.md           ← Agent identity card
├── nemoclaw-config.yaml      ← Sandbox configuration
├── network-policy.yaml       ← Deny-by-default egress rules
├── deploy.sh                 ← One-command deployment script
└── README.md                 ← Setup and deploy instructions
```

## Workspace Files

### SKILL.md

Same format as OpenClaw SKILL.md — YAML frontmatter with name/description, followed by the system prompt, knowledge, tools, and guardrails sections.

```markdown
---
name: my-agent
description: A helpful agent
---

You are a helpful assistant.

## Knowledge
- **docs** (file): /tmp/docs.md

## Tools
- **gh** (shell): GitHub CLI

## Guardrails
- Never share private keys
```

### SOUL.md

Agent persona extracted from the IR:

```markdown
# SOUL.md - Agent Persona

## Core Identity
<personality_notes or default>

## Boundaries
- <guardrail 1>
- <guardrail 2>

## Vibe
Professional, reliable, task-focused.
```

### IDENTITY.md

Agent identity card:

```markdown
# IDENTITY.md

- **Name:** my-agent
- **Creature:** AI agent
- **Vibe:** <first line of personality_notes or "Helpful and focused">
- **Emoji:** 🤖
```

## nemoclaw-config.yaml Schema

```yaml
sandbox:
  name: <string>           # Agent name from IR
  description: <string>    # Truncated to 100 chars

inference:
  provider: nvidia          # nvidia | anthropic | openai | ollama

workspace:
  upload_on_deploy: true
  files:
    - workspace/SKILL.md
    - workspace/SOUL.md
    - workspace/IDENTITY.md

security:
  posture: balanced         # strict | balanced | developer
  operator_approval: true   # Require approval for new network destinations
```

## network-policy.yaml Schema

NemoClaw uses **deny-by-default** egress. The network policy defines which endpoints are allowed.

```yaml
policies:
  - name: <policy_name>
    endpoints: [<host:port>, ...]
    binaries: [<path_to_binary>, ...]
```

### Default Policies

Every NemoClaw agent gets these base policies:

| Policy | Endpoints | Binary |
|--------|-----------|--------|
| `claude_code` | `api.anthropic.com:443` | `/usr/local/bin/claude` |
| `nvidia` | `integrate.api.nvidia.com:443`, `inference-api.nvidia.com:443` | `/usr/local/bin/openclaw` |

### Tool-Based Policy Generation

| IR Tool | Policy Generated |
|---------|-----------------|
| `gh` or `git` (shell) | `github` → `api.github.com:443`, `github.com:443` |
| `npm` or `node` (shell) | `npm_registry` → `registry.npmjs.org:443` |
| `curl` or `wget` (shell) | Commented `# TODO` block for manual configuration |
| Any MCP tool | Commented `# TODO` block for MCP endpoint configuration |

## IR → NemoClaw Mapping

| IR Field | NemoClaw Output |
|----------|-----------------|
| `ir.name` | `nemoclaw-config.yaml: sandbox.name`, SKILL.md frontmatter, IDENTITY.md |
| `ir.description` | `nemoclaw-config.yaml: sandbox.description` (100 char max), SKILL.md |
| `ir.persona.system_prompt` | workspace/SKILL.md body |
| `ir.persona.personality_notes` | workspace/SOUL.md Core Identity, IDENTITY.md Vibe |
| `ir.tools` | workspace/SKILL.md Tools section, network-policy.yaml |
| `ir.knowledge` | workspace/SKILL.md Knowledge section |
| `ir.governance.guardrails` | workspace/SKILL.md Guardrails, workspace/SOUL.md Boundaries |
| `ir.metadata.emoji` | workspace/IDENTITY.md Emoji |

## Deploy Instructions

### Prerequisites

1. Install NemoClaw CLI: `curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash`
2. Start OpenShell gateway: `openshell gateway start`

### Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

The deploy script:
1. Checks `nemoclaw` CLI is installed
2. Checks OpenShell gateway is running
3. Creates the sandbox with config and network policy
4. Uploads workspace files to `/sandbox/.openclaw/workspace/`

### Connect

```bash
nemoclaw <agent-name> connect
```
