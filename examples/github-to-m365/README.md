# github — Microsoft 365 Declarative Agent

GitHub operations via `gh` CLI: issues, PRs, CI runs, code review, API queries. Use when: (1) checking PR status or CI, (2) creating/commenting on issues, (3) listing/filtering PRs or issues, (4) viewing run logs. NOT for: complex web UI interactions requiring manual browser flows (use browser tooling when available), bulk operations across many repos (script with gh api), or when gh auth is not configured.

> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**

## Generated Files

| File | Description |
|------|-------------|
| `declarative-agent.json` | Agent manifest with instructions and capabilities |
| `manifest.json` | Teams app manifest referencing the declarative agent |
| `README.md` | This file |

## Conversion Notes

### Dropped Shell Tools

The following shell tools have no M365 equivalent and were dropped:

- `gh` — TODO: implement manually if needed
- `git` — TODO: implement manually if needed

## Prerequisites

- Microsoft 365 tenant with Copilot license
- Admin access to Teams Admin Center or Microsoft 365 Developer Portal
- Two icon files: `color.png` (192x192 px) and `outline.png` (32x32 px)

## Deploy

### 1. Add Icons

Place your `color.png` and `outline.png` icons in this directory.
Teams Toolkit provides default icons if you don't have custom ones.

### 2. Package

```bash
zip -j agent-package.zip declarative-agent.json manifest.json color.png outline.png
```

### 3. Upload

Upload via **Teams Admin Center**:
- Go to **Teams apps > Manage apps > Upload new app**
- Select `agent-package.zip`

Or use the **Microsoft 365 Developer Portal**:
- Visit https://dev.teams.microsoft.com/
- Import the app package

### 4. (Optional) Teams Toolkit

If you use VS Code with Teams Toolkit:
```bash
teamsapp package
teamsapp deploy
```

## About

This agent was automatically converted using AgentShift.

- **Source format:** OpenClaw SKILL.md
- **Target format:** Microsoft 365 Declarative Agent
- **Converter:** [AgentShift](https://agentshift.sh)

To convert other OpenClaw skills:
```bash
agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to m365 --output /tmp/m365-output
```