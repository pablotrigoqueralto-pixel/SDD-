# Tasks — production-deployment

scope: backend=true, frontend=false · design-linked: false. Work is infrastructure/pipeline/ops configuration; `[BE]` covers backend tooling and infra files. The live premiere against the real VM is executed by the operator following the runbook — apply verifies everything locally verifiable.

## 1. Backend tooling

- [x] 1.1 [TEST][BE] Write failing unit tests for `app/tooling/bootstrap_admin.py` (creates an admin from `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD`, validates the password, idempotent re-run resets the password without duplicating the user), then implement it reusing the existing `ensure_admin` logic and make `e2e_seed` consume the shared function.

## 2. Production infrastructure

- [x] 2.1 [BE] Create `deploy/docker-compose.prod.yml`: caddy/db/migrate/backend/frontend on `ghcr.io` images parameterised by `IMAGE_TAG`, `${VAR:?}` for all secrets (no dev fallbacks), `restart: unless-stopped`, existing healthchecks, json-file log rotation (10m/5), only caddy publishing 80/443. Verify: `docker compose -f ... config` fails naming `JWT_SECRET` when unset and renders cleanly with a full env; grep confirms no dev JWT/password literal and no `build:` key.
- [x] 2.2 [BE] Create `deploy/Caddyfile` (crm.quermed.com, `/api/*` and `/health` → backend:8000, rest → frontend:8080, automatic HTTPS) and validate its syntax with `caddy validate` in a container; rehearse the routing locally with a host-file alias and Caddy's internal TLS to prove both upstreams answer through one origin.
- [x] 2.3 [BE] Add the production env inventory and server prerequisites to `development_guide.md` (VM provisioning, firewall 22/80/443, deploy user, `/opt/quermed-crm/` layout, DNS-before-first-boot) and gitignore any local production env file.

## 3. Deployment pipeline

- [x] 3.1 [BE] Add the image-publish job to GitHub Actions: on push to `main` only, build backend and frontend (frontend with `VITE_API_URL=https://crm.quermed.com`), push to GHCR tagged `<sha>` and `latest` using the built-in token.
- [x] 3.2 [BE] Add the `deploy` job targeting the `production` environment (required reviewer = one-click approval): SSH into the server, `compose pull` the release tag, `compose run --rm migrate`, `compose up -d`, curl the public `/health` and fail the job on a bad response. Document the rollback-by-previous-SHA procedure and its forward-only-migrations caveat.
- [x] 3.3 [TEST][BE] Prove the pipeline wiring: workflow YAML passes CI's own validation on the PR run, the PR run publishes no images, and (after merge) the publish job's condition is asserted by inspection in the PR description/checklist.

## 4. Operations

- [x] 4.1 [BE] Write `deploy/backup.sh` (pg_dump -Fc to `/var/backups/quermed-crm/` dated, prune >30 days, rclone copy to the external remote, non-zero exit on any failure) plus the cron installation line; rehearse dump+prune locally against the dev db container using a local-directory rclone remote.
- [x] 4.2 [TEST][BE] Rehearse the restore for real: seed the local stack with data, take a dump with the script, destroy the volume, `pg_restore --clean --if-exists` into a fresh db, and verify health plus restored records through the API; record the rehearsal in the design's implementation notes and write the restore runbook in `development_guide.md`.
- [x] 4.3 [BE] Document in `development_guide.md`: uptime-monitor enrolment (poll `https://crm.quermed.com/health` ≤5 min, email alert), the Graph go-live tenant procedure ending in the test-quote-with-`sent`-outbox verification, and the ordered go-live checklist (provision → DNS → env → first deploy → bootstrap_admin → territories/users/settings → Graph live + test quote → monitor enrolled → backup verified → imports by back office → reps onboarded).

## 5. Validation

- [x] 5.1 [TEST][BE] Quality gates: full backend suite green (bootstrap_admin tests included), ruff + mypy clean; dev compose smoke and the complete Playwright suite (desktop + mobile, rate-limit swap) to prove zero regressions from the tooling change.
- [x] 5.2 [BE] Coherence pass: `api-spec.yml` and `data-model.md` show no diff (no API/schema change), `development_guide.md` production sections read top-to-bottom as one runbook, and the deploy/ files are referenced from it.
