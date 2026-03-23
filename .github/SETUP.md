# GitHub Repository Setup (Manual Steps)

These settings require admin access and can't be set via the current CLI token.

## 1. Repository Settings

Go to **Settings → General**:

- [x] Description: "CLI transpiler for converting AI agents between platforms"
- [x] Enable Discussions
- [x] Enable Issues
- [x] Disable Wiki (not needed — docs live in repo)
- [x] Allow auto-merge
- [x] Automatically delete head branches after merge

## 2. Branch Protection Rules

Go to **Settings → Branches → Add rule**:

**Branch name pattern:** `main`

- [x] Require a pull request before merging
  - [x] Require approvals: **1**
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] Require review from Code Owners
- [x] Require status checks to pass before merging
  - [x] Require branches to be up to date before merging
  - Required checks:
    - `Lint`
    - `Test (Python 3.12)`
    - `Build package`
- [x] Require conversation resolution before merging
- [ ] Do NOT require signed commits (keeps barrier low for contributors)
- [x] Do not allow force pushes
- [x] Do not allow deletions

## 3. Labels

Create these labels in **Issues → Labels**:

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | `#d73a4a` | Something isn't working |
| `enhancement` | `#a2eeef` | New feature or request |
| `platform-request` | `#0075ca` | Request for a new platform |
| `good first issue` | `#7057ff` | Good for newcomers |
| `help wanted` | `#008672` | Extra attention is needed |
| `triage` | `#e4e669` | Needs triage |
| `parser` | `#1d76db` | Related to a parser |
| `emitter` | `#1d76db` | Related to an emitter |
| `ir-schema` | `#d876e3` | Related to the IR schema |
| `cli` | `#bfd4f2` | Related to the CLI |
| `docs` | `#0075ca` | Documentation |
| `wontfix` | `#ffffff` | This will not be worked on |

## 4. Enable GitHub Discussions

Go to **Settings → General → Features**:
- [x] Discussions

Create these discussion categories:
- **Announcements** (maintainers only)
- **Ideas** (open)
- **Q&A** (open, answer-markable)
- **Show and Tell** (open)
