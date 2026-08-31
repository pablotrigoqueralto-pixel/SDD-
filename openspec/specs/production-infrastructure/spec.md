# production-infrastructure

## Purpose
The production runtime on one VM: standalone hardened Compose file on published images, Caddy terminating HTTPS for the single crm.quermed.com origin, fail-fast secret handling outside git and documented server prerequisites.

## Requirements

### Requirement: Standalone production Compose file
The repository SHALL provide `deploy/docker-compose.prod.yml`, independent of the development compose file, defining `caddy`, `db`, `migrate`, `backend` and `frontend`. Application services SHALL reference published images (`ghcr.io/...:<tag>` via an `IMAGE_TAG` variable), never `build:` contexts. All long-running services SHALL set `restart: unless-stopped`, keep the existing healthchecks, and cap logs via the json-file driver (`max-size` 10m, `max-file` 5). `migrate` SHALL remain the one-shot Alembic+seed runner gating `backend` start. Only `caddy` SHALL publish host ports (80 and 443); `db` SHALL NOT publish 5432.

#### Scenario: No build on the server
- **WHEN** `deploy/docker-compose.prod.yml` is inspected
- **THEN** no service carries a `build:` key and every app image is a `ghcr.io` reference parameterised by tag

#### Scenario: Database unreachable from outside
- **WHEN** the production stack is up
- **THEN** port 5432 is not bound on the host and PostgreSQL is reachable only on the compose network

#### Scenario: Crash self-heals
- **WHEN** the backend container exits unexpectedly
- **THEN** Docker restarts it (`unless-stopped`) and the healthcheck reports it healthy again without operator action

### Requirement: Fail-fast secrets, no development defaults
The production Compose file SHALL take every secret and environment value from an env file kept outside git (`/opt/quermed-crm/.env`, chmod 600) using `${VAR:?}` syntax for required values — it SHALL NOT inherit the development fallbacks (dev JWT secret, `crm` password, permissive CORS). The documented inventory SHALL cover at least: `POSTGRES_PASSWORD`, `JWT_SECRET`, `CORS_ORIGINS` (only `https://crm.quermed.com`), `ENVIRONMENT=prod`, `AUTH_RATE_LIMIT=10/minute`, `WEB_CONCURRENCY`, `IMAGE_TAG`, `GRAPH_SENDER_MODE`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`. `.gitignore` SHALL exclude any local copy of the production env file.

#### Scenario: Missing secret aborts startup
- **WHEN** `docker compose -f deploy/docker-compose.prod.yml config` runs without `JWT_SECRET` defined
- **THEN** compose fails with an error naming the variable instead of silently using a default

#### Scenario: No dev fallback survives
- **WHEN** the production compose file is searched for the development JWT default or the `crm` password fallback
- **THEN** no such literal exists in the file

### Requirement: Caddy terminates HTTPS for a single origin
`deploy/Caddyfile` SHALL serve `crm.quermed.com` with automatic Let's Encrypt certificates (issuance and renewal handled by Caddy), proxying `/api/*` and `/health` to `backend:8000` and every other path to `frontend:8080`. HTTP SHALL redirect to HTTPS. The production frontend image SHALL be built with `VITE_API_URL=https://crm.quermed.com` so browser and API share one origin.

#### Scenario: API and app under one domain
- **WHEN** a client requests `https://crm.quermed.com/api/v1/reference-data` and `https://crm.quermed.com/hoy`
- **THEN** the first is answered by the backend and the second by the frontend, both over TLS on the same origin

#### Scenario: Health through the proxy
- **WHEN** the uptime monitor requests `https://crm.quermed.com/health`
- **THEN** the backend health payload is returned through Caddy

#### Scenario: Plain HTTP redirected
- **WHEN** a client requests `http://crm.quermed.com/`
- **THEN** it receives a redirect to the `https://` URL

### Requirement: Documented server prerequisites
The development guide SHALL document VM provisioning: Docker Engine with the compose plugin, a non-root deploy user in the `docker` group, firewall allowing only 22/80/443, the DNS A record for `crm.quermed.com` created before first boot, and the `/opt/quermed-crm/` layout (compose file, Caddyfile, env file, backup script).

#### Scenario: Fresh VM to running stack
- **WHEN** an operator follows the provisioning section on a clean VM
- **THEN** every command needed to reach a healthy first deployment appears in order, with no undocumented step
