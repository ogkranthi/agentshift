# AGENTS.md → Any Platform

Guide for converting AGENTS.md files to any supported AgentShift target.

---

## What is AGENTS.md?

`AGENTS.md` is a convention used in 60,000+ GitHub repositories to describe AI agent behavior. It typically contains sections like:

- Agent name and description
- Instructions and constraints
- Tool usage guidelines
- Knowledge sources

AgentShift can parse AGENTS.md and convert it to any supported output format.

---

## How AgentShift parses it

AgentShift maps AGENTS.md sections to its intermediate representation (IR):

| AGENTS.md section | IR field |
|---|---|
| Title / heading | `identity.name` |
| Description paragraph | `identity.description` |
| Instructions / behavior | `instructions` |
| Tools / capabilities | `tools` |
| Constraints / rules | `constraints` |
| Knowledge / context | `knowledge` |

The parser recognizes common heading patterns (`## Instructions`, `## Tools`, `## Rules`, etc.) and maps them to the appropriate IR fields. Unrecognized sections are preserved in the instructions body.

---

## Usage

### Convert to Claude Code

```bash
agentshift convert . --from agents-md --to claude-code --output ./claude-output
```

### Convert to any target

```bash
agentshift convert . --from agents-md --to copilot --output ./copilot-output
agentshift convert . --from agents-md --to bedrock --output ./bedrock-output
agentshift convert . --from agents-md --to nemoclaw --output ./nemoclaw-output
```

### Check portability

```bash
agentshift diff . --from agents-md
```

---

## Example: AGENTS.md → CLAUDE.md

### Input: AGENTS.md

```markdown
# Code Review Agent

Reviews pull requests for code quality, security issues, and style compliance.

## Instructions

- Review each file in the PR diff
- Flag security issues (SQL injection, XSS, hardcoded secrets)
- Check for style guide violations
- Provide actionable suggestions, not just complaints

## Tools

- gh (GitHub CLI)
- git

## Constraints

- Never approve PRs automatically
- Always explain the reasoning behind each flag
```

### Output: CLAUDE.md

```markdown
# Code Review Agent

Reviews pull requests for code quality, security issues, and style compliance.

## Instructions

- Review each file in the PR diff
- Flag security issues (SQL injection, XSS, hardcoded secrets)
- Check for style guide violations
- Provide actionable suggestions, not just complaints

## Constraints

- Never approve PRs automatically
- Always explain the reasoning behind each flag

## Tools

- **gh** (shell): Run gh commands
- **git** (shell): Run git commands
```

### Output: settings.json

```json
{
  "permissions": {
    "allow": [
      "Bash(gh:*)",
      "Bash(git:*)"
    ]
  }
}
```

---

## Tips

- AgentShift looks for `AGENTS.md` in the root of the directory you pass. Make sure the file exists at the top level.
- If your AGENTS.md uses non-standard headings, the content is still preserved — it just goes into the instructions body rather than a specific IR field.
- Use `agentshift diff` to see how well your AGENTS.md maps to each target before converting.
