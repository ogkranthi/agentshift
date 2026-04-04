# AgentShift Portability Report — GitHub Action

Automatically analyze AI agent portability across Claude Code, Copilot, Bedrock, M365, and Vertex AI. Posts a portability report as a PR comment.

## Quick Start

Add to any workflow (5 lines):

```yaml
- name: Agent Portability Report
  uses: agentshift/agentshift/.github/actions/portability-report@main
  with:
    targets: claude-code,copilot,bedrock,m365,vertex
```

## Full Example

```yaml
name: Agent Portability Check
on: [pull_request]

jobs:
  portability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Agent Portability Report
        id: report
        uses: agentshift/agentshift/.github/actions/portability-report@main
        with:
          targets: claude-code,copilot,bedrock
          comment-on-pr: "true"
      - name: Check score
        run: |
          echo "Average portability: ${{ steps.report.outputs.average-score }}%"
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `github-token` | `${{ github.token }}` | GitHub token for PR comments |
| `targets` | `claude-code,copilot,bedrock,m365,vertex` | Comma-separated target platforms |
| `comment-on-pr` | `true` | Post report as PR comment |

## Outputs

| Output | Description |
|---|---|
| `average-score` | Average portability score (0-100) |

## What It Detects

The action automatically finds agent definitions in your repository:

- `CLAUDE.md` — Claude Code agent instructions
- `AGENTS.md` — Community standard agent definitions
- `SKILL.md` — OpenClaw skill definitions
- `*.agent.md` — GitHub Copilot agent files

## Report Format

The PR comment includes a portability matrix showing conversion fidelity per platform, an average score, and notes about components that require manual work.
