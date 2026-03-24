# Examples

Real skill conversions from OpenClaw to Claude Code and GitHub Copilot format.

| Skill | Claude Code | GitHub Copilot |
|---|---|---|
| weather | [examples/weather-to-claude-code/](weather-to-claude-code/) | [examples/weather-to-copilot/](weather-to-copilot/) |
| github | [examples/github-to-claude-code/](github-to-claude-code/) | [examples/github-to-copilot/](github-to-copilot/) |
| slack | [examples/slack-to-claude-code/](slack-to-claude-code/) | [examples/slack-to-copilot/](slack-to-copilot/) |
| notion | [examples/notion-to-claude-code/](notion-to-claude-code/) | — |

Each example contains an `input/` directory with the original OpenClaw skill and an `output/` directory with the converted files.

```bash
# Try it yourself
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to claude-code --output ./out-claude
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to copilot --output ./out-copilot
```
