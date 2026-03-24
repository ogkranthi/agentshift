# weather — GitHub Copilot Agent

Get current weather and forecasts via wttr.in or Open-Meteo. Use when: user asks about weather, temperature, or forecasts for any location. NOT for: historical weather data, severe weather alerts, or detailed meteorological analysis. No API key needed.

> **Converted from OpenClaw by [AgentShift](https://github.com/agentshift/agentshift)**

## Installation

### VS Code (recommended)

1. Open VS Code.
2. Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`).
3. Run **GitHub Copilot: Install Agent from File**.
4. Select `weather.agent.md` from this directory.
5. The agent will appear in the Copilot Chat agent picker (`@` menu).

### Manual install

Copy the `.agent.md` file to your VS Code user agents directory:

- **macOS/Linux:** `~/.vscode/extensions/github.copilot-*/agents/`
- **Windows:** `%USERPROFILE%\.vscode\extensions\github.copilot-*\agents\`

Or place it in your workspace at `.github/copilot-agents/` to share with your team.

## About

This agent was automatically converted from an OpenClaw skill using AgentShift.

- **Source format:** OpenClaw SKILL.md
- **Target format:** GitHub Copilot `.agent.md`
- **Converter:** [AgentShift](https://github.com/agentshift/agentshift)

To convert other OpenClaw skills:
```bash
agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to copilot --output /tmp/copilot-output
```