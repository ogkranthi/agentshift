# Examples

Real skill conversions from OpenClaw to Claude Code, GitHub Copilot, AWS Bedrock, Microsoft 365, and GCP Vertex AI format.

## Conversion Matrix

| Skill | Claude Code | GitHub Copilot | Bedrock | M365 | Vertex AI |
|---|---|---|---|---|---|
| pregnancy-companion | [output/claude-code](pregnancy-companion-output/claude-code/) | [output/copilot](pregnancy-companion-output/copilot/) | [output/bedrock](pregnancy-companion-output/bedrock/) | [output/m365](pregnancy-companion-output/m365/) | [output/vertex](pregnancy-companion-output/vertex/) |
| weather | [weather-to-claude-code/](weather-to-claude-code/) | [weather-to-copilot/](weather-to-copilot/) | [weather-to-bedrock/](weather-to-bedrock/) | — | [weather-to-vertex/](weather-to-vertex/) |
| github | [github-to-claude-code/](github-to-claude-code/) | [github-to-copilot/](github-to-copilot/) | [github-to-bedrock/](github-to-bedrock/) | [github-to-m365/](github-to-m365/) | [github-to-vertex/](github-to-vertex/) |
| slack | [slack-to-claude-code/](slack-to-claude-code/) | [slack-to-copilot/](slack-to-copilot/) | [slack-to-bedrock/](slack-to-bedrock/) | — | — |
| notion | [notion-to-claude-code/](notion-to-claude-code/) | — | — | — | — |

The `pregnancy-companion/` directory contains the original OpenClaw source skill.
`pregnancy-companion-output/` contains the generated output for all 5 platforms.

---

## Regenerating examples

### Convert

```bash
# Convert a single skill to one target
agentshift convert examples/pregnancy-companion --from openclaw --to claude-code --output ./out

# Convert to all targets at once
agentshift convert examples/pregnancy-companion --from openclaw --to all --output examples/pregnancy-companion-output

# Regenerate a specific example pair
agentshift convert examples/pregnancy-companion --from openclaw --to bedrock --output examples/pregnancy-companion-output/bedrock
```

### Diff (portability matrix)

```bash
# Show what converts cleanly vs. what needs manual work
agentshift diff examples/pregnancy-companion --from openclaw

# Diff against specific targets only
agentshift diff examples/pregnancy-companion --from openclaw --targets claude-code,copilot,bedrock
```

### Validate

```bash
# Validate a generated config against its platform schema
agentshift validate examples/pregnancy-companion-output/claude-code --target claude-code
agentshift validate examples/pregnancy-companion-output/copilot --target copilot
agentshift validate examples/pregnancy-companion-output/bedrock --target bedrock
agentshift validate examples/pregnancy-companion-output/m365 --target m365
agentshift validate examples/pregnancy-companion-output/vertex --target vertex

# Machine-readable JSON report
agentshift validate examples/pregnancy-companion-output/claude-code --target claude-code --json
```

### MCP-to-OpenAPI

```bash
# Generate an OpenAPI 3.0 schema from MCP/shell tools
agentshift mcp-to-openapi examples/pregnancy-companion --from openclaw
agentshift mcp-to-openapi examples/pregnancy-companion --from openclaw --output openapi.json
```

---

## Verbose / debug output

Add `--verbose` before any subcommand to see full debug output including the parsed IR:

```bash
agentshift --verbose convert examples/pregnancy-companion --from openclaw --to all --output ./out
agentshift --verbose diff examples/pregnancy-companion --from openclaw
```
