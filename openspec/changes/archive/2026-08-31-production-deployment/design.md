## Context

The repository already ships everything a production deployment consumes: a Compose stack (db + one-shot `migrate` service + backend with `/health` healthcheck + frontend image with `VITE_API_URL` baked as a build arg), settings that read every secret from the environment (`ENVIRONMENT` already accepts `prod`, `GRAPH_SENDER_MODE` accepts `off`/`graph`), CI that lints, tests and runs Playwright against the stack, and an idempotent reference-data seed. What is missing is the production shape around it: a hardened Compose overlay, TLS on a real domain, published images, an approval-gated deploy path, backups, monitoring and the go-live runbook. No application feature changes.

scope:
  backend: true
  frontend: false
design-linked: false

## Goals / Non-Goals

**Goals:**
- One VM serving `https://crm.quermed.com` with automatic certificates and the whole app under a single origin.
- Releases traceable to a commit: images built by CI, deployed over SSH after a one-click approval, migrations applied by the same mechanism already used locally.
- Survive a dead disk: nightly dumps, 30-day retention, daily external copy, and a restore procedure that has actually been executed.
- Know it is down before the users call: external uptime alerting on `/health`.
- Quotes emailed for real through Graph from each rep's mailbox.

**Non-Goals:** everything listed in the proposal (SSO, staging, observability stack, PITR, HA, historic migration) — plus no Kubernetes, no Terraform/IaC: one pet VM documented step by step is the right size for this MVP.

## Decisions

### D1. Caddy as reverse proxy, whole app under one origin

`deploy/` gains a `Caddyfile` and a production Compose file where Caddy is the only service publishing ports (80/443). Caddy terminates TLS for `crm.quermed.com` with automatic Let's Encrypt issuance and renewal, proxies `/api/*` and `/health` to `backend:8000` and everything else to `frontend:8080`. The frontend image is built with `VITE_API_URL=https://crm.quermed.com`, so browser and API share one origin — CORS stops being a production concern (the allowlist still carries only that origin as defence in depth) and cookies stay first-party.

- **Discarded — Traefik**: label-driven config shines with many services; for three containers it is more moving parts than a 15-line Caddyfile.
- **Discarded — nginx + certbot**: two components and a renewal cron to own versus Caddy's built-in ACME.
- **Discarded — exposing backend and frontend on separate subdomains**: reintroduces CORS, doubles certificates and DNS entries, zero benefit.

### D2. Production Compose file in `deploy/`, images pulled — never built — on the server

`deploy/docker-compose.prod.yml` is a standalone file (not an override of the dev one): services `caddy`, `db`, `migrate`, `backend`, `frontend` referencing `ghcr.io/<owner>/quermed-crm-{backend,frontend}:<tag>`, `restart: unless-stopped` everywhere (except one-shot `migrate`), the existing healthchecks, `logging` driver options (`max-size: 10m`, `max-file: 5`), no source mounts, no dev defaults: every secret comes from `/opt/quermed-crm/.env` (chmod 600, outside git) and the file fails fast if a required variable is missing (no `:-` fallbacks for secrets). `db` stops publishing 5432 to the host.

- **Discarded — override file on top of dev compose**: inheriting dev defaults (weak JWT fallback, published DB port, build contexts) is exactly what production must not do; an explicit file is auditable at a glance.
- **Discarded — building images on the VM**: needs the source tree and toolchain on the server, produces unrepeatable artifacts and slow deploys.

### D3. CI publishes images; deploy is a gated workflow over SSH

The existing `ci.yml` gains (or a sibling `deploy.yml` provides) two steps on push to `main`: build backend and frontend images (frontend with the production `VITE_API_URL` build arg) and push them to GHCR tagged `latest` and the commit SHA, authenticated with the built-in `GITHUB_TOKEN`. A `deploy` job then targets the GitHub `production` environment configured with a required reviewer — the one-click manual approval — and, once approved, connects over SSH (host/user/key from Actions secrets) and runs the release sequence on the server: `docker compose pull`, `docker compose run --rm migrate`, `docker compose up -d`, followed by a curl against `/health`. Rolling back is re-running the deploy job of the previous commit (its SHA-tagged images are immutable in GHCR).

- **Discarded — auto-deploy on every merge**: the user chose an approval gate; merges land while a rep may be mid-quote.
- **Discarded — pull-based agents (watchtower)**: silent unattended upgrades with no approval, no migration ordering and no audit trail.
- **Discarded — a separate registry (Docker Hub/ACR)**: GHCR is zero extra accounts and free for this scale.

### D4. Secrets inventory, not secret management

Production values live in exactly two places: `/opt/quermed-crm/.env` on the VM and GitHub Actions secrets (`DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_KEY`). The server env inventory is documented (POSTGRES_PASSWORD, JWT_SECRET, CORS_ORIGINS, GRAPH_TENANT_ID/CLIENT_ID/CLIENT_SECRET, GRAPH_SENDER_MODE, AUTH_RATE_LIMIT=10/minute, ENVIRONMENT=prod, WEB_CONCURRENCY) with generation guidance (e.g. `openssl rand`), never values.

- **Discarded — Azure Key Vault / SOPS**: worthwhile with more operators or more environments; today it adds an auth dependency to every deploy for one file on one server.

### D5. Backups: cron + `pg_dump -Fc` + rclone copy, restore actually rehearsed

`deploy/backup.sh` (installed as a root cron entry at 03:30 Europe/Madrid): `docker compose exec -T db pg_dump -Fc` to `/var/backups/quermed-crm/quermed_crm_<date>.dump`, prune files older than 30 days, then `rclone copy` the new dump to an Azure Blob container in the Quermed tenant (rclone remote configured once on the server). The script exits non-zero on any step failing so cron mails the error. The restore runbook (`pg_restore --clean --if-exists` into the db container, then health + spot checks) is executed once for real during apply — against the local stack with a production-shaped dump — so the procedure is proven, not aspirational.

- **Discarded — WAL archiving/PITR**: the user accepted a nightly loss window; PITR's operational complexity is the whole reason.
- **Discarded — Azure CLI upload**: rclone keeps the target swappable and the script provider-agnostic; `az` drags a large dependency onto the VM for one command.

### D6. Monitoring: external uptime + what the stack already carries

An external uptime monitor (healthchecks.io/UptimeRobot free tier) polls `https://crm.quermed.com/health` every 1–5 minutes and emails on failure — the only component that can notice the whole VM going dark. Inside the VM nothing new: container healthchecks and `restart: unless-stopped` self-heal crashes, the backend's structured JSON logs rotate via the Docker logging options, and the backup cron mails its own failures.

- **Discarded — Sentry/Grafana/Prometheus**: explicitly out of scope by decision; the failure modes that matter at this scale (VM down, container crash-loop, disk full, backup failing) are all covered by the above plus the runbook's disk check.

### D7. Graph goes live as configuration

Production sets `GRAPH_SENDER_MODE=graph` (the settings enum's exact live value) with the tenant's credentials. The tenant procedure is documentation, not code: app registration, application permission `Mail.Send` with admin consent, and a New-ApplicationAccessPolicy scoping the app to the sales mailboxes' mail-enabled security group. The failure path needs nothing new — change 07 already records `mail_outbox` rows and offers retry, and a misconfigured tenant degrades to visible errors on the quote sheet, never to unsent-looking quotes.

### D8. First admin via a real bootstrap command

The E2E seeding tool already contains a correct, idempotent `ensure_admin` (validated password, real Argon2 hash). It is promoted to an honestly named production entrypoint — `python -m app.tooling.bootstrap_admin` reading `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD` — with the E2E tool reusing the same function. This is the change's only touch inside `backend/app` and alters no runtime behaviour. After first login the admin creates territories and users from the existing admin screens; the go-live checklist then hands back office the change-08 importers for catalogue and accounts.

- **Discarded — documenting the E2E tool as the production bootstrap**: shipping `e2e_seed` in a production runbook invites cargo-culting E2E variables into production.
- **Discarded — SQL insert runbook**: hand-built Argon2 hashes in a wiki page is exactly how a company locks itself out.

## Risks / Trade-offs

- [Single VM is a single point of failure] → accepted for MVP scale; tested restore + published images mean rebuild-from-scratch is a documented sub-hour path, and the uptime monitor bounds detection time.
- [Let's Encrypt issuance fails at first boot (DNS not propagated)] → the runbook orders DNS before first `up` and includes the Caddy log check; Caddy retries issuance on its own.
- [Migrations run against the live DB during deploy] → same Alembic path exercised on every local boot and CI run since change 01; deploys happen after approval, and the nightly dump plus an optional pre-deploy manual dump bound the blast radius.
- [Baked `VITE_API_URL` couples the frontend image to the domain] → acceptable: one production domain; a domain change is a rebuild, which the pipeline makes a one-click affair.
- [rclone remote or Blob credentials rot silently] → the backup script fails loudly (cron mail) if the copy step fails; the monthly checklist item re-verifies a restorable dump exists off-site.

## Migration Plan

1. Provision the VM (Docker + compose plugin, firewall allowing 22/80/443, non-root deploy user in the `docker` group) and point `crm.quermed.com` at it.
2. Place `/opt/quermed-crm/.env` from the documented inventory; configure the rclone remote; install the backup cron.
3. First release: approve the deploy workflow (pull, migrate+seed, up); run `bootstrap_admin`; verify `/health` through the domain and enrol the uptime monitor.
4. Go-live checklist: admin creates territories/users/settings, sets Graph credentials live and sends a test quote; back office imports the Sage catalogue and the accounts Excel via the change-08 screens; reps onboard.
5. Rollback at any point = approve the deploy job of the previous SHA; data rollback = documented restore procedure.

## Open Questions

None — hosting, domain, SSO deferral, Graph activation, backup policy, monitoring depth, deploy gating and go-live data strategy were all settled in the pre-proposal question rounds.

## Implementation notes (recorded during /opsx:apply)

- Restore rehearsal executed for real on 2026-08-31: seeded the local stack with a marker account, dumped with the script's exact `pg_dump -Fc` command, copied via an rclone container to a local-directory remote, destroyed the volume (`down -v`), restored with `pg_restore --clean --if-exists` and verified health, admin login and the marker account through the API.
- Lesson from the rehearsal: on a brand-new cluster the dump's GRANTs fail because role `crm_app` (created by migration 0001) does not exist yet — the restore runbook gained an explicit `CREATE ROLE crm_app NOLOGIN` step for disaster recovery; restores into the existing production database are unaffected.
- The Caddyfile routing was rehearsed locally with a `localhost` site and Caddy's internal CA on the dev compose network: `/health` answered by the backend, `/` by the frontend and `/api/v1/...` by the backend through one TLS origin.
- `bootstrap_admin` refactors `ensure_admin` to take a session (testable under the savepoint fixtures); `e2e_seed` now wraps the same `run()` with its E2E defaults.
- The publish and deploy jobs live in one `deploy.yml`: `workflow_dispatch` with an `image_tag` input doubles as the rollback path (publish is skipped, deploy reuses the immutable SHA images).
- Git Bash path mangling (MSYS) bites any `docker ... /path` argument on this machine — rehearsal commands needed `MSYS_NO_PATHCONV=1`; the server-side scripts are unaffected (Linux).
