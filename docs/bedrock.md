# OpenClaw → AWS Bedrock

Full end-to-end guide for converting an OpenClaw skill to AWS Bedrock Agent format.

---

## Step 1: Convert

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to bedrock --output ./github-bedrock
```

Output:

```
github-bedrock/
├── instruction.txt        ← system prompt (≤4,000 chars, Bedrock instruction field)
├── instruction-full.txt   ← only if the prompt was truncated
├── openapi.json           ← OpenAPI 3.0 action group schema
├── cloudformation.yaml    ← full CF template (Agent + Alias + ActionGroups)
└── README.md              ← prerequisites + deploy command
```

---

## Step 2: Prerequisites

- AWS account with Bedrock enabled in your region
- IAM role with `bedrock:InvokeModel` permission
- Lambda functions for each action group (stub ARNs are in CloudFormation — replace with real ones)
- Claude 3.5 Sonnet model enabled in your region

---

## Step 3: Deploy

```bash
aws cloudformation deploy \
  --template-file github-bedrock/cloudformation.yaml \
  --stack-name agentshift-github \
  --parameter-overrides AgentRoleArn=<your-role-arn> \
  --capabilities CAPABILITY_IAM
```

---

## Step 4: Invoke

```bash
aws bedrock-agent-runtime invoke-agent \
  --agent-id <AgentId from CF outputs> \
  --agent-alias-id <AliasId from CF outputs> \
  --session-id session-1 \
  --input-text "List open PRs for owner/repo"
```

---

## What carries over from OpenClaw

| OpenClaw feature | Bedrock equivalent | Status |
|---|---|---|
| Skill instructions (body) | `instruction.txt` — loaded as agent instruction | ✅ Full fidelity (≤4,000 chars) |
| Shell tools (gh, curl, etc.) | Lambda action groups (stub ARNs) | ⚠️ You must implement the Lambda |
| MCP tools | Action group (stub) | ⚠️ Manual implementation required |
| Knowledge files | S3 knowledge base (stub) | ⚠️ S3 upload + KB setup required |
| Cron / scheduled triggers | EventBridge rule (stub) | ⚠️ Wire to your EventBridge schedule |
| Telegram / Slack delivery | Not supported natively | ❌ |

---

## Limitations

- **4,000 char instruction limit** — long skills get truncated (see `instruction-full.txt` for the complete version)
- **Shell tools become Lambda stubs** — tools like `gh` or `curl` are represented as action groups; you must implement the Lambda function backing each one
- **No native cron** — use EventBridge rules to trigger the agent on a schedule
- **No Telegram/Slack delivery** — Bedrock agents return responses via API; push delivery requires a separate integration

---

## Check portability first

```bash
agentshift diff ~/.openclaw/skills/github --from openclaw --targets bedrock
```

---

See also: [examples/github-to-bedrock/](../examples/github-to-bedrock/)
