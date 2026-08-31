## Why

Changes 01–09 delivered a feature-complete CRM that only runs on developer machines and CI. Quermed's reps, managers and back office cannot use it until it lives on a real server with a real address, survives a disk failure, and can be updated safely. This change takes the proven Docker Compose stack to production and closes the MVP.

scope:
  backend: true
  frontend: false
design-linked: false

(The work is infrastructure, pipeline and operations configuration; the application code itself does not change. Frontend involvement is limited to production build configuration inside the existing images, so no UI capability is declared.)

## What Changes

- Production runtime on a single VM: a hardened production Compose configuration (pinned images, restart policies, resource limits, log rotation, no source mounts, secrets from an env file kept out of git) behind a reverse proxy terminating HTTPS for `crm.quermed.com` with automatic Let's Encrypt certificates.
- Container images built and published by CI on every merge to `main` (GitHub Container Registry), replacing "build on the server".
- A deploy job in GitHub Actions gated by one-click manual approval: connects to the server over SSH, pulls the released images, runs Alembic migrations and restarts the stack — traceable, repeatable releases.
- Nightly `pg_dump` backups with 30-day retention on the server and a daily copy to external storage in the Microsoft tenant; the restore procedure is documented and actually exercised as part of this change.
- Basic monitoring: an external uptime check against `/health` alerting by email, container health checks with automatic restart, and structured logs with rotation.
- Microsoft Graph mail switched live: documented tenant activation (app registration with application `Mail.Send`, admin consent, application access policy scoped to sales mailboxes) and production configuration `GRAPH_SENDER_MODE=live` so quotes go out from each rep's own mailbox.
- Go-live runbook: server provisioning steps, DNS, first-boot sequence, creation of real territories/users/settings, initial data load through the change-08 importers (Sage catalogue, accounts/contacts Excel) and a launch checklist.

## Capabilities

### New Capabilities
- `production-infrastructure`: the production runtime — production Compose file, reverse proxy with automatic HTTPS, environment/secret handling, container hardening (restart, healthchecks, log rotation, no dev artifacts) and server prerequisites.
- `deployment-pipeline`: image publishing from CI on merge to `main` and the approval-gated deploy job that ships images to the server and applies migrations.
- `operations`: backups with tested restore, uptime monitoring with email alerts, log retention, the Graph go-live tenant procedure and the go-live checklist with initial data load.

### Modified Capabilities

(None — no application requirement changes. The existing `project-scaffolding` spec keeps describing the development stack; production concerns live in the new capabilities.)

## Non-goals

- No Entra ID SSO — production launches with the existing email+password login; OIDC is its own post-MVP change (the user model already carries `identity_provider`).
- No staging environment; the environments are local development and production.
- No Sentry/Grafana/Prometheus observability stack — uptime, healthchecks and logs only.
- No PITR/WAL archiving — nightly dumps with external copy are the accepted loss window.
- No high availability, autoscaling or multi-node topology — one VM serves the MVP's user count.
- No historic data migration from Sage beyond the catalogue and accounts/contacts loads already supported by the importers.
- No application features, API changes or schema changes of any kind.

## Impact

- **Roles**: no behavioural change for any role; territory visibility rules are untouched. Operationally, `admin` performs the go-live configuration and `back_office` runs the initial imports — both using screens that already exist.
- **Repository**: new `deploy/` directory (production Compose file, proxy configuration, backup script, server notes), new/extended GitHub Actions workflow (image publish + gated deploy), no changes under `backend/app` or `frontend/src` expected.
- **Docs**: `development_guide.md` gains the production sections (provisioning, deploy, backups/restore, monitoring, Graph activation, go-live checklist). `api-spec.yml` and `data-model.md` untouched — no API or schema changes.
- **Secrets**: production env values (DB password, JWT secret, Graph credentials, registry token, SSH key) live only on the server and in GitHub Actions secrets; the change defines their inventory, never their values.
- **Constitution principles served**: mobile-first reach (reps use the CRM from the street over HTTPS on a real domain), reliability and data safety (tested backups, healthchecks, restart policies), incremental delivery (approval-gated repeatable deploys of the already-verified stack), security baseline (TLS everywhere, secrets out of git, hardened containers, rate limits back to production values).
