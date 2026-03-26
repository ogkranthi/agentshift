# pregnancy-companion — Microsoft 365 Declarative Agent

24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey

> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**

## Generated Files

| File | Description |
|------|-------------|
| `declarative-agent.json` | Agent manifest with instructions and capabilities |
| `manifest.json` | Teams app manifest referencing the declarative agent |
| `README.md` | This file |

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