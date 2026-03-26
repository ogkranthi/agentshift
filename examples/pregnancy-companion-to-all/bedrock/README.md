# pregnancy-companion — AWS Bedrock Agent

24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey

> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**

## Generated Files

| File | Description |
|------|-------------|
| `instruction.txt` | Agent system prompt (≤ 4,000 chars, Bedrock limit) |
| `openapi.json` | OpenAPI 3.0 action group schema for all tools |
| `cloudformation.yaml` | CloudFormation template to provision the Bedrock agent |
| `README.md` | This file — setup and deploy instructions |

> **Note:** If your agent's system prompt exceeds 4,000 characters, an
> `instruction-full.txt` is also written with the complete untruncated text.

## Prerequisites

Before deploying, complete these steps:

### 1. IAM Role

Create an IAM role with the `AmazonBedrockAgentResourcePolicy` managed policy
and `bedrock:InvokeModel` permissions. Pass its ARN as the `AgentRoleArn` parameter.

```bash
aws iam create-role --role-name agentshift-bedrock-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "bedrock.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

### 3. Knowledge Bases

Your agent uses knowledge sources. Each requires a Bedrock Knowledge Base
backed by an S3 bucket and a vector store (OpenSearch Serverless or similar).

Knowledge bases referenced in `cloudformation.yaml` (replace `kb-PLACEHOLDER-TODO`):

- **appointments** (file) — Knowledge file: appointments.md
- **exercise** (file) — Knowledge file: exercise.md
- **nutrition** (file) — Knowledge file: nutrition.md
- **warning-signs** (file) — Knowledge file: warning-signs.md
- **week-by-week** (file) — Knowledge file: week-by-week.md

See the [Bedrock Knowledge Bases guide](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html) for setup instructions.

## Deploy

```bash
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name agentshift-pregnancy-companion \
  --parameter-overrides AgentRoleArn=<YOUR_ROLE_ARN> \
  --capabilities CAPABILITY_IAM
```

After deployment, retrieve the agent and alias IDs:

```bash
aws cloudformation describe-stacks --stack-name agentshift-pregnancy-companion \
  --query 'Stacks[0].Outputs'
```

## Invoke the Agent

```bash
aws bedrock-agent-runtime invoke-agent \
  --agent-id <AgentId> \
  --agent-alias-id <AliasId> \
  --session-id session-$(date +%s) \
  --input-text 'Hello!'
```

## About

This agent was automatically converted using AgentShift.

- **Source format:** OpenClaw SKILL.md
- **Target format:** AWS Bedrock Agent (CloudFormation)
- **Converter:** [AgentShift](https://agentshift.sh)

To convert other OpenClaw skills:
```bash
agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to bedrock --output /tmp/bedrock-output
```