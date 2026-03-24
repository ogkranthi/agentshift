# Examples

Real skill conversions from OpenClaw to Claude Code, GitHub Copilot, and AWS Bedrock format.

| Skill | Claude Code | GitHub Copilot | Bedrock |
|---|---|---|---|
| weather | [examples/weather-to-claude-code/](weather-to-claude-code/) | [examples/weather-to-copilot/](weather-to-copilot/) | [examples/weather-to-bedrock/](weather-to-bedrock/) |
| github | [examples/github-to-claude-code/](github-to-claude-code/) | [examples/github-to-copilot/](github-to-copilot/) | [examples/github-to-bedrock/](github-to-bedrock/) |
| slack | [examples/slack-to-claude-code/](slack-to-claude-code/) | [examples/slack-to-copilot/](slack-to-copilot/) | [examples/slack-to-bedrock/](slack-to-bedrock/) |
| notion | [examples/notion-to-claude-code/](notion-to-claude-code/) | — | — |

Each example contains an `input/` directory with the original OpenClaw skill and an `output/` directory with the converted files.

```bash
# Try it yourself
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to claude-code --output ./out-claude
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to copilot --output ./out-copilot
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to bedrock --output ./out-bedrock
```
