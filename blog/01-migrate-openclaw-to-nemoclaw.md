---
title: "Migrating Your OpenClaw Agents to NVIDIA NemoClaw: One Command, Any Cloud"
published: true
description: "NVIDIA just launched NemoClaw — hardened sandboxes for OpenClaw agents. Here's how to migrate your entire OpenClaw setup in one command with AgentShift."
tags: nvidia, ai, agents, devops
cover_image: https://agentshift.sh/og-nemoclaw.png
canonical_url: https://agentshift.sh
---

NVIDIA launched NemoClaw on March 16 and the developer community moved fast. NemoClaw wraps your OpenClaw agents in hardened OpenShell sandboxes — Landlock/seccomp isolation, deny-by-default network policies, and local NVIDIA Nemotron inference. It's the enterprise-grade way to run always-on AI agents.

The problem: migrating from OpenClaw to NemoClaw manually means copying each skill, writing network policies per tool, re-registering every cron job, and setting up cloud deploy scripts. For most setups that's 10-20 skills and dozens of scheduled jobs.

I built [AgentShift](https://agentshift.sh) to do it in one command.

## The migration command

```bash
pip install agentshift

agentshift migrate --source ~/.openclaw --to nemoclaw --cloud aws --output ./migration
```

That's it. Here's what it does:

```
AgentShift migrate ~/.openclaw (openclaw) → nemoclaw (cloud: aws)
Migrating... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Migration complete!
  Skills: 14/14 migrated
  Cron jobs: 19/19 migrated
  Network policies: generated (12 unique endpoints)

✓ Output → ./migration/
  Report: ./migration/MIGRATION_REPORT.md
  Deploy:  ./migration/deploy/aws/userdata.sh
```

## What gets generated

```
migration/
├── workspace/
│   ├── skills/           ← all your skills, ready to upload
│   ├── SOUL.md
│   ├── MEMORY.md         ← copied with review warning
│   └── IDENTITY.md
├── nemoclaw-config.yaml  ← sandbox config with inference provider
├── network-policy.yaml   ← merged egress rules for ALL your tools
├── cron-migration.sh     ← re-register all 19 cron jobs
├── deploy/
│   └── aws/
│       ├── userdata.sh   ← paste into EC2 launch config
│       └── README.md
└── MIGRATION_REPORT.md   ← what migrated, what needs manual steps
```

## Network policies — the clever part

NemoClaw uses deny-by-default egress. Every endpoint your agent hits needs to be explicitly allowed. AgentShift reads your skills' tool lists and generates the policies automatically.

If you have a GitHub skill using `gh` and `git`:
```yaml
- name: github
  endpoints:
    - api.github.com:443
    - github.com:443
  binaries:
    - /usr/local/bin/gh
    - /usr/bin/git
```

If you have a weather skill using `curl`:
```yaml
# TODO [agentshift]: Replace with real endpoint for tool 'curl'
# - name: custom_curl
#   endpoints: [your-api-endpoint:443]
```

The policies are merged and deduplicated across all your skills. If five skills use `curl`, you get one policy entry.

## Cron jobs

NemoClaw uses OpenShell's policy system for scheduling. AgentShift reads your `~/.openclaw/cron/jobs.json` and generates re-registration commands:

```bash
# cron-migration.sh
openshell policy cron add \
  --agent "github-reviewer" \
  --schedule "0 * * * *" \
  --message "Check for open PRs..." \
  --session-target "isolated"
```

All 19 jobs, exact schedules preserved. Delivery channel configs (Telegram bot tokens) are intentionally not migrated — NemoClaw strips credentials for security, and you re-enter them during `nemoclaw onboard`.

## Cloud targets

```bash
# AWS EC2
agentshift migrate --cloud aws   # → deploy/aws/userdata.sh

# Google Cloud
agentshift migrate --cloud gcp   # → deploy/gcp/startup-script.sh

# Azure
agentshift migrate --cloud azure # → deploy/azure/cloud-init.yaml

# Docker
agentshift migrate --cloud docker # → deploy/docker/docker-compose.yml

# Bare metal
agentshift migrate --cloud bare-metal # → deploy.sh
```

## Before you migrate: check portability

```bash
agentshift diff ~/.openclaw/skills/github --from openclaw
```

```
  Component      claude-code  copilot  bedrock  nemoclaw
  ─────────────────────────────────────────────────────
  Instructions   ✅ 100%      ✅ 100%  ✅ 100%  ✅ 100%
  Tools (shell)  ✅ Bash(*)   ✅ term  ❌ stub   ✅ policy
  ─────────────────────────────────────────────────────
  Portability    100%         92%      38%       95%
```

NemoClaw scores 95% vs Bedrock's 38% — because shell tools stay shell tools, just policy-gated.

## MIGRATION_REPORT.md

The report tells you exactly what needs attention:

```markdown
## ✅ Skills migrated (14/14)
## ⚠️ Manual steps required
- Re-enter Telegram bot token during `nemoclaw onboard`
- Re-enter GitHub token for gh CLI
## ❌ Not portable
- imsg skill — macOS only, sandbox is Linux
```

## Get started

```bash
pip install agentshift
agentshift migrate --source ~/.openclaw --to nemoclaw --cloud aws
```

Docs: [agentshift.sh/docs/nemoclaw](https://github.com/ogkranthi/agentshift/blob/main/docs/nemoclaw.md)
GitHub: [github.com/ogkranthi/agentshift](https://github.com/ogkranthi/agentshift)
