# slack — GitHub Copilot Agent

Use when you need to control Slack from OpenClaw via the slack tool, including reacting to messages or pinning/unpinning items in Slack channels or DMs.

> **Converted from OpenClaw by [AgentShift](https://github.com/agentshift/agentshift)**

## Installation

### VS Code (recommended)

1. Open VS Code.
2. Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`).
3. Run **GitHub Copilot: Install Agent from File**.
4. Select `slack.agent.md` from this directory.
5. The agent will appear in the Copilot Chat agent picker (`@` menu).

### Manual install

Copy the `.agent.md` file to your VS Code user agents directory:

- **macOS/Linux:** `~/.vscode/extensions/github.copilot-*/agents/`
- **Windows:** `%USERPROFILE%\.vscode\extensions\github.copilot-*\agents\`

Or place it in your workspace at `.github/copilot-agents/` to share with your team.

## MCP Servers Required

This agent uses MCP (Model Context Protocol) tools that require server-side configuration.
Add the following to your VS Code `settings.json`:

```json
"github.copilot.chat.agent.mcp.server": {
  "slack": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-slack"]
  },
}
```

> **Note:** Exact server configuration depends on the MCP server package.
> Consult each server's documentation for the correct `command` and `args`.

## About

This agent was automatically converted from an OpenClaw skill using AgentShift.

- **Source format:** OpenClaw SKILL.md
- **Target format:** GitHub Copilot `.agent.md`
- **Converter:** [AgentShift](https://github.com/agentshift/agentshift)

To convert other OpenClaw skills:
```bash
agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to copilot --output /tmp/copilot-output
```