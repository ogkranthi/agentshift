# Examples

Real skill conversions from OpenClaw to Claude Code, GitHub Copilot, AWS Bedrock, Microsoft 365, and GCP Vertex AI format.

| Skill | Claude Code | GitHub Copilot | Bedrock | M365 | Vertex AI |
|---|---|---|---|---|---|
| weather | [examples/weather-to-claude-code/](weather-to-claude-code/) | [examples/weather-to-copilot/](weather-to-copilot/) | [examples/weather-to-bedrock/](weather-to-bedrock/) | — | [examples/weather-to-vertex/](weather-to-vertex/) |
| github | [examples/github-to-claude-code/](github-to-claude-code/) | [examples/github-to-copilot/](github-to-copilot/) | [examples/github-to-bedrock/](github-to-bedrock/) | [examples/github-to-m365/](github-to-m365/) | [examples/github-to-vertex/](github-to-vertex/) |
| slack | [examples/slack-to-claude-code/](slack-to-claude-code/) | [examples/slack-to-copilot/](slack-to-copilot/) | [examples/slack-to-bedrock/](slack-to-bedrock/) | — | — |
| notion | [examples/notion-to-claude-code/](notion-to-claude-code/) | — | — | — | — |

Each example contains an `input/` directory with the original OpenClaw skill and an `output/` directory with the converted files.

```bash
# Try it yourself
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to claude-code --output ./out-claude
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to copilot --output ./out-copilot
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to bedrock --output ./out-bedrock
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to m365 --output ./out-m365
agentshift convert ~/.openclaw/skills/<name> --from openclaw --to vertex --output ./out-vertex
```
