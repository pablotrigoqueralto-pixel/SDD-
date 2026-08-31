# deployment-pipeline

## Purpose
Immutable images published to GHCR on merge to main and an approval-gated GitHub Actions deploy over SSH that pulls, migrates and restarts the stack, with rollback by redeploying a previous SHA.

## Requirements

### Requirement: Images published on merge to main
On every push to `main`, GitHub Actions SHALL build the backend and frontend images and push them to GitHub Container Registry authenticated with the workflow's built-in token. Each image SHALL be tagged with both the commit SHA and `latest`; the frontend build SHALL receive `VITE_API_URL=https://crm.quermed.com` as its build argument. Image publishing SHALL NOT run for pull requests.

#### Scenario: Merge produces immutable artifacts
- **WHEN** a PR is squash-merged to `main`
- **THEN** `ghcr.io` holds backend and frontend images tagged with that merge commit's SHA and `latest` points at them

#### Scenario: Pull requests build nothing
- **WHEN** CI runs for a pull request
- **THEN** no image is pushed to the registry

### Requirement: Deploy gated by one-click approval
Deployment SHALL be a GitHub Actions job targeting the `production` environment configured with a required reviewer, so a release reaches the server only after an explicit approval in the GitHub UI. Once approved, the job SHALL connect to the server over SSH (host, user and private key from Actions secrets) and execute the release sequence in `/opt/quermed-crm/`: `docker compose pull` with the release tag, `docker compose run --rm migrate`, `docker compose up -d`, then verify `https://crm.quermed.com/health` responds OK — a failing verification SHALL fail the job.

#### Scenario: No approval, no deploy
- **WHEN** images are published for a merge but nobody approves the production environment
- **THEN** the deploy job stays pending and the server keeps running the previous release

#### Scenario: Approved release applies migrations first
- **WHEN** the reviewer approves the deploy
- **THEN** the server pulls the SHA-tagged images, runs the one-shot migrate service to completion and only then restarts the stack

#### Scenario: Broken release fails loudly
- **WHEN** the post-deploy health verification does not return OK
- **THEN** the workflow run is marked failed and the failure is visible in Actions

### Requirement: Rollback by redeploying a previous SHA
The pipeline SHALL support rolling back by running the deploy job with a previous commit's SHA tag (images in the registry are immutable). The procedure SHALL be documented next to the deploy instructions, including the caveat that migrations are forward-only and a data rollback is the restore procedure, not the pipeline.

#### Scenario: Redeploy yesterday's build
- **WHEN** the operator triggers the deploy for the prior release's SHA
- **THEN** the server runs that exact image pair again without rebuilding anything
