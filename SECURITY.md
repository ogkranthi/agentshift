# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Instead, please report security vulnerabilities via GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/ogkranthi/agentshift/security) of this repository
2. Click "Report a vulnerability"
3. Provide a description of the vulnerability and steps to reproduce

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Security Considerations

AgentShift processes agent definitions that may contain:

- **Credentials and API keys** — AgentShift should never include credentials in generated output. If you find a case where it does, report it immediately.
- **System prompts** — These are copied between formats. AgentShift does not evaluate or execute them.
- **File paths** — Parsers read from the local filesystem. Path traversal issues should be reported.
- **Generated configs** — Emitters write files to disk. Ensure output directories are as expected.

## Scope

The following are in scope for security reports:

- Credential leakage in generated configs
- Path traversal in parsers or emitters
- Code injection via malformed agent definitions
- Dependency vulnerabilities

The following are out of scope:

- Security of the target platforms themselves (Copilot, Bedrock, Vertex AI, etc.)
- Vulnerabilities in agent definitions being converted (we don't evaluate agent logic)
