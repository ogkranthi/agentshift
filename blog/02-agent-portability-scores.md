---
title: "Why Your AI Agent Is 38% Portable to AWS Bedrock (and What to Do About It)"
published: true
description: "Most agent conversion tools just copy your instructions. AgentShift measures portability before you convert — so you know what you're getting."
tags: aws, ai, openai, github
cover_image: https://agentshift.sh/og-portability.png
canonical_url: https://agentshift.sh
---

I've been converting AI agents between platforms for a few months and the most common surprise is this: developers assume their agent will work the same everywhere. It won't.

Here's a real example. Take a GitHub skill from OpenClaw — it uses `gh` CLI commands, reads PR diffs, posts comments. Run `agentshift diff` on it:

```bash
agentshift diff ~/.openclaw/skills/github --from openclaw
```

```
  github — Portability Report

  Component       Source   claude-code   copilot   bedrock   nemoclaw
  ─────────────────────────────────────────────────────────────────────
  Instructions      ✅      ✅ 100%      ✅ 100%   ⚠️ trunc   ✅ 100%
  Tools (shell: 2)  ✅      ✅ Bash(gh)  ✅ term   ❌ dropped  ✅ policy
  Constraints       ✅      ✅ supported ⚠️ stub   ⚠️ stub    ✅ full
  ─────────────────────────────────────────────────────────────────────
  Portability                 100%         92%       38%        95%
```

**38% on Bedrock.** Why?

## What kills portability: shell tools

OpenClaw and Claude Code agents run shell commands directly. `gh pr list`, `curl`, `ffmpeg` — these are just subprocess calls. The agent has full access to the host's binaries.

AWS Bedrock doesn't have a shell. It has Lambda functions and OpenAPI action groups. When you convert a shell-heavy agent to Bedrock, every tool becomes a Lambda stub:

```yaml
# Generated cloudformation.yaml
ActionGroups:
  - ActionGroupName: github-gh
    ActionGroupExecutor:
      Lambda: arn:aws:lambda:...  # TODO: implement this
    # TODO [agentshift]: Shell tool 'gh' has no native Bedrock equivalent.
    # Implement the tool logic in the Lambda above.
```

The instructions convert perfectly (100%). But if 60% of what your agent *does* is run shell commands, 60% of it now requires Lambda implementations. Hence 38%.

## The three portability layers

AgentShift tracks governance across three layers:

**L1 — Prompt guardrails (always 100%)**
Your safety rules, disclaimers, scope limits — these live in the system prompt and always transfer. If your agent says "never provide medical advice", that survives every conversion.

**L2 — Tool permissions (37-100% depending on target)**
Deny lists, binary restrictions, file access controls. Claude Code gets precise `Bash(gh:*)` permissions. NemoClaw gets network policies. Bedrock gets Lambda stubs. Copilot gets `execute/runInTerminal`.

**L3 — Platform-native controls (0% natively, 93.6% via elevation)**
Bedrock has native guardrails (topic blocks, PII detection). Vertex has safety settings. These don't exist in OpenClaw's format — but AgentShift elevates them to prompt-level instructions that produce equivalent behavior.

```bash
agentshift audit ./my-agent --from openclaw --targets claude-code,bedrock

  Target        GPR-L1   GPR-L2   GPR-L3   Overall
  ────────────────────────────────────────────────────
  Claude Code    1.00     0.93     0.00*     0.83
  Bedrock        1.00     0.37     0.00*     0.62
  * L3 elevated to prompt instructions (93.6% behavioral equivalence)
```

## How to improve Bedrock portability

If you're converting to Bedrock and want better than 38%, the strategies are:

**1. Replace shell tools with API calls**
Instead of `gh pr list` (subprocess), use the GitHub REST API directly. Bedrock can call REST APIs natively via action groups. AgentShift generates the OpenAPI schema — you just need to wire the Lambda.

**2. Use knowledge bases for knowledge files**
OpenClaw reads local markdown files. Bedrock has native Knowledge Bases backed by S3 + vector search. AgentShift flags the knowledge files and generates the KB stub in CloudFormation.

**3. Accept the stubs, implement incrementally**
The generated `cloudformation.yaml` has every tool as a stub with `# TODO` comments. Deploy it, test the instruction-only behavior, then implement tools one by one.

## Checking portability before you convert

The key workflow is: **diff first, then convert**.

```bash
# See scores across all platforms
agentshift diff ./my-skill --from openclaw

# Convert only to platforms where the score is acceptable
agentshift convert ./my-skill --from openclaw --to claude-code --output ./out

# Validate the output before deploying
agentshift validate ./out/claude-code --target claude-code
```

For the EU AI Act (enforcement August 2026), there's also a compliance check:

```bash
agentshift compliance ./my-skill --from openclaw --framework eu-ai-act
```

This checks Art. 9 (safety guardrails), Art. 13 (transparency), Art. 14 (human oversight), Art. 52 (AI disclosure).

## The portability matrix

Here's how different skill types score across platforms:

| Skill type | Claude Code | Copilot | Bedrock | NemoClaw |
|---|---|---|---|---|
| Instructions-only | 100% | 100% | 100% | 100% |
| Shell CLI tools | 100% | 92% | 38% | 95% |
| MCP tools | 100% | 88% | 50% | 100% |
| Knowledge files | 95% | 90% | 55% | 95% |
| Cron triggers | 85% | 30% | 45% | 90% |

The pattern: **NemoClaw and Claude Code are the most portable targets** because they preserve shell access. Bedrock is the hardest because it's a managed service with no direct shell.

---

AgentShift is open source. Try it:

```bash
pip install agentshift
agentshift diff ./my-agent --from openclaw
```

GitHub: [github.com/ogkranthi/agentshift](https://github.com/ogkranthi/agentshift)
