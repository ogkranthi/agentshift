# slack — AWS Bedrock Agent

Use when you need to control Slack from OpenClaw via the slack tool, including reacting to messages or pinning/unpinning items in Slack channels or DMs.

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

### 2. Lambda Functions (Action Groups)

Each tool in your agent requires a Lambda function to handle invocations.
The CloudFormation template references placeholder ARNs marked with `# TODO`.

Create a Lambda function for each action group below:

- **slack-slack** — implements `slack` (mcp tool)

The Lambda handler contract (Bedrock → Lambda request/response format) is
documented in the [Bedrock Developer Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-lambda.html).

## Deploy

```bash
aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name agentshift-slack \
  --parameter-overrides AgentRoleArn=<YOUR_ROLE_ARN> \
  --capabilities CAPABILITY_IAM
```

After deployment, retrieve the agent and alias IDs:

```bash
aws cloudformation describe-stacks --stack-name agentshift-slack \
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