# AgentShift Sync — GitHub Action

## What it does

The **AgentShift Sync** workflow automatically converts every `SKILL.md` file in your repository into cloud-ready agent configs whenever one of those files changes on `main` or `master`.

For each skill directory it discovers, the action runs:

```sh
agentshift convert --from openclaw --to all <skill_dir> --output <skill_dir>/agentshift-output
```

Generated configs are committed back to the same branch by `github-actions[bot]`, so your repo always contains up-to-date configs without any manual steps.

If any conversion fails, the action automatically opens a GitHub Issue with a summary of what failed and links to the full logs.

---

## How to use it in your own repo

1. **Copy the workflow file** into your repo:

   ```
   .github/workflows/agentshift-sync.yml
   ```

2. **Ensure your repo has `SKILL.md` files** in one or more skill directories. The action finds all `**/SKILL.md` files automatically (excluding `tests/`).

3. **Push to `main` or `master`.** The workflow triggers automatically whenever a `SKILL.md` file changes.

4. Optionally run it manually via the **Actions → AgentShift Sync → Run workflow** button with custom inputs.

### Required permissions

The workflow needs write access to push the generated configs back to the branch. This is granted automatically via the default `GITHUB_TOKEN` — no secrets to configure.

If your repo has branch protection rules that block `github-actions[bot]` commits, add an exception or use a PAT with `contents: write` stored as `secrets.GH_PAT` and replace `secrets.GITHUB_TOKEN` in the `checkout` step.

---

## Configuration options (workflow_dispatch inputs)

When triggering manually via `workflow_dispatch`, you can override:

| Input | Default | Description |
|---|---|---|
| `targets` | `all` | Comma-separated target platforms to generate (e.g. `claude-code,copilot`). Use `all` for every supported target. |
| `output_dir` | `agentshift-output` | Name of the output subdirectory created inside each skill directory. |
| `skill_pattern` | `**/SKILL.md` | Glob pattern used to locate skill files (relative to repo root). |

### Supported target platforms

| Key | Output |
|---|---|
| `claude-code` | `.claude/` with `CLAUDE.md` and tool stubs |
| `copilot` | `.github/copilot-instructions.md` |
| `bedrock` | AWS Bedrock agent action group JSON |
| `m365` | Microsoft 365 Copilot declarative agent manifest |
| `vertex` | Google Vertex AI agent YAML |
| `all` | All of the above |

---

## Example output structure

Given a repo layout like:

```
my-repo/
├── skills/
│   └── researcher/
│       └── SKILL.md
└── SKILL.md
```

After the action runs, the structure becomes:

```
my-repo/
├── skills/
│   └── researcher/
│       ├── SKILL.md
│       └── agentshift-output/          ← generated
│           ├── claude-code/
│           │   ├── CLAUDE.md
│           │   └── tools/
│           ├── copilot/
│           │   └── copilot-instructions.md
│           ├── bedrock/
│           │   └── action-group.json
│           ├── m365/
│           │   └── declarative-agent.json
│           └── vertex/
│               └── agent.yaml
├── SKILL.md
└── agentshift-output/                  ← generated (root skill)
    ├── claude-code/
    └── ...
```

---

## Failure handling

When a conversion fails the action:

1. **Continues** processing remaining skills (partial success is still committed).
2. **Opens a GitHub Issue** titled `AgentShift Sync failed on <sha>: N skill(s) errored`.
3. The issue body includes:
   - Which skill directories failed
   - A direct link to the failed workflow run
   - Reproduction steps for local debugging

To reproduce locally:

```sh
pip install agentshift
agentshift convert --from openclaw --to all ./path/to/skill --output ./path/to/skill/agentshift-output
```

---

## Skipping CI on generated commits

Generated-config commits include `[skip ci]` in the message, so they won't trigger a recursive workflow run.

---

## Local development

Install agentshift and run conversions locally before pushing:

```sh
pip install agentshift
# Convert a single skill
agentshift convert --from openclaw --to all ./my-skill --output ./my-skill/agentshift-output
# Convert to a specific target only
agentshift convert --from openclaw --to claude-code ./my-skill --output ./my-skill/agentshift-output
```

See `agentshift --help` for all options.
