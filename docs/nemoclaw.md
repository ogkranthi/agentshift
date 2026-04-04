# OpenClaw → NVIDIA NemoClaw

Full end-to-end guide for converting OpenClaw skills to NVIDIA NemoClaw sandboxed deployment.

---

## Step 1: Convert a single skill

```bash
agentshift convert ./my-skill --from openclaw --to nemoclaw --output ./my-skill-nemoclaw
```

Output:

```
my-skill-nemoclaw/
├── workspace/
│   ├── SKILL.md           ← converted instructions
│   ├── SOUL.md            ← guardrails and persona
│   └── IDENTITY.md        ← agent identity metadata
├── nemoclaw-config.yaml   ← NemoClaw runtime configuration
├── network-policy.yaml    ← deny-by-default network rules
├── deploy.sh              ← deployment script
└── README.md              ← quickstart instructions
```

---

## Step 2: Full migration (entire OpenClaw install)

```bash
agentshift migrate --source ~/.openclaw --to nemoclaw --cloud aws --output ./migration
```

This scans your entire OpenClaw installation — all skills, 19+ cron jobs — and generates:

- One NemoClaw workspace per skill
- `cron-migration.sh` for all scheduled triggers
- Cloud-specific deploy files (CloudFormation, Terraform, Docker Compose, etc.)
- `MIGRATION_REPORT.md` with per-skill status

See [docs/migrate.md](migrate.md) for full details on the `migrate` command.

---

## Step 3: Deploy

### Docker

```bash
cd ./migration
docker compose up -d
```

### AWS EC2

Paste `userdata.sh` into your EC2 launch configuration:

```bash
aws ec2 run-instances \
  --image-id ami-xxxxxxxx \
  --instance-type g5.xlarge \
  --user-data file://migration/userdata.sh
```

### GCP Compute Engine

```bash
gcloud compute instances create nemoclaw-agent \
  --metadata-from-file startup-script=migration/startup-script.sh \
  --machine-type n1-standard-4 \
  --zone us-central1-a
```

### Bare metal

```bash
bash deploy.sh
```

---

## Step 4: Verify

```bash
nemoclaw <name> connect
```

This opens an interactive session with your migrated agent to confirm everything is working.

---

## What carries over from OpenClaw

| Feature | Preserved? | Notes |
|---|---|---|
| Instructions | ✅ 100% | SKILL.md body |
| Tool permissions | ✅ | Network policies auto-generated |
| Cron triggers | ✅ | `cron-migration.sh` generated |
| Knowledge files | ✅ | Paths updated for sandbox |
| Credentials | ❌ | Re-enter during `nemoclaw onboard` — by design |
| macOS-only skills | ❌ | Skipped — sandbox is Linux |
| Telegram delivery | ⚠️ | Works but re-configure bot token |

---

## What you gain with NemoClaw

NemoClaw provides capabilities beyond what OpenClaw offered:

- **Sandboxed execution** — Landlock/seccomp isolation for every agent
- **Deny-by-default network policies** — auto-generated from your skill's tool usage
- **Local inference** — run NVIDIA Nemotron models locally, no API calls required
- **State management** — built-in migration snapshots and rollback
- **Cloud-native deployment** — first-class support for AWS, GCP, Azure, and Docker

---

## Check portability first

```bash
agentshift diff ./my-skill --from openclaw --targets nemoclaw
```
