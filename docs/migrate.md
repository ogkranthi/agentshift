# agentshift migrate

Full guide for migrating an entire OpenClaw installation to a new platform.

---

## What it does

`agentshift migrate` scans your OpenClaw directory and performs four steps:

1. **Scan** — discovers all skills, cron jobs, knowledge files, and configuration
2. **Convert** — runs `agentshift convert` on each skill
3. **Merge** — combines cron jobs into `cron-migration.sh`, aggregates network policies
4. **Generate** — produces cloud-specific deploy files based on your `--cloud` target

---

## Usage

```bash
agentshift migrate --source ~/.openclaw --to nemoclaw --cloud <target> --output ./migration
```

---

## Cloud options

| `--cloud` | What it generates |
|---|---|
| `aws` | CloudFormation template, `userdata.sh` for EC2, IAM role stubs |
| `gcp` | `startup-script.sh` for Compute Engine, Terraform config |
| `azure` | ARM template, `cloud-init.yaml` for Azure VMs |
| `docker` | `docker-compose.yaml`, Dockerfile, volume mounts |
| `bare-metal` | `deploy.sh` shell script, systemd unit files |

---

## Output structure

```
migration/
├── skills/
│   ├── weather/            ← one workspace per skill
│   ├── github/
│   └── ...
├── cron-migration.sh       ← all cron jobs from jobs.json
├── network-policy.yaml     ← aggregated deny-by-default rules
├── deploy.sh               ← cloud-specific deploy script
├── docker-compose.yaml     ← (docker only)
├── cloudformation.yaml     ← (aws only)
├── MIGRATION_REPORT.md     ← per-skill conversion status
└── README.md               ← quickstart instructions
```

---

## How to read MIGRATION_REPORT.md

The migration report contains a summary table:

```
Skill               Status    Notes
────────────────────────────────────────
weather             ✅ OK
github              ✅ OK
daily-standup       ✅ OK     cron migrated
macos-clipboard     ⚠️ SKIP   macOS-only — sandbox is Linux
telegram-bot        ✅ OK     re-configure bot token manually
────────────────────────────────────────
Total: 19 skills | 17 converted | 2 skipped
Cron jobs: 19 migrated → cron-migration.sh
```

Each skill shows its conversion status, any warnings, and what needs manual attention.

---

## What always needs manual steps

| Item | Why | What to do |
|---|---|---|
| Credentials | Never copied — security by design | Re-enter during `nemoclaw onboard` |
| Telegram bot tokens | Token is per-deployment | Re-configure in NemoClaw settings |
| macOS-only skills | NemoClaw sandbox is Linux | Rewrite or skip |

---

## FAQ

**What about my MEMORY.md?**
Copied to the new workspace with a warning. Memory files may reference OpenClaw-specific paths — review and update after migration.

**What about cron jobs?**
All cron jobs from `jobs.json` are converted to `cron-migration.sh`. Run it on the target host to install crontab entries. Each entry points to the migrated skill's workspace.

**Can I migrate to multiple clouds at once?**
Run `migrate` once per `--cloud` target. Each output directory is self-contained.

**What if a skill fails to convert?**
It appears as `⚠️ SKIP` in `MIGRATION_REPORT.md` with the reason. The migration continues — skipped skills don't block other conversions.
