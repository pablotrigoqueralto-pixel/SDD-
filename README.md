# 🚀 OpenSpecs SDD System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

### Spec-Driven Development + AI Governance Layer

This repository implements a customized OpenSpecs workflow enhanced with
an AI governance layer.

It enforces:

-   Explicit technical standards
-   Deterministic documentation structure
-   Controlled change lifecycle
-   Spec‑Driven Development (SDD)
-   AI‑governed architectural discipline

------------------------------------------------------------------------

# 🧠 What Is This?

This is not just an OpenSpecs setup.

It is a governed development environment composed of:

-   OpenSpecs (workflow orchestration)
-   Custom Claude commands
-   Explicit backend & frontend standards
-   Documentation enforcement rules
-   Structured templates
-   Blocking policies for incomplete work

The goal is to eliminate architectural drift and documentation entropy.

------------------------------------------------------------------------

# 📐 Development Model: Spec‑Driven Development (SDD)

Specifications are the source of truth.\
Code is an implementation artifact.

The order of operations:

1.  Define or update specs
2.  Apply change
3.  Verify artifacts & tasks
4.  Update documentation
5.  Archive change

No direct coding outside this flow.

------------------------------------------------------------------------

# 🏗 Project Architecture

- `.claude/commands/opsx/` → OpenSpecs workflow commands
- `.claude/commands/ai-specs/` → Governance & standards commands
- `ai-specs/` → Specs, templates, standards, docs
- `openspec/` → OpenSpecs CLI workflow

openspec/ → OpenSpecs CLI workflow

------------------------------------------------------------------------

# 🔄 Command Domains

Commands are organized by namespace.

## 🔄 /opsx:\* --- OpenSpecs Workflow

Lifecycle management commands:

-   /opsx:new --- Start a new change
-   /opsx:ff --- Fast‑forward creation of artifacts
-   /opsx:apply --- Implement change artifacts
-   /opsx:verify --- Verify implementation vs artifacts
-   /opsx:sync --- Sync delta specs into main specs
-   /opsx:continue --- Continue experimental workflow
-   /opsx:archive --- Archive completed change
-   /opsx:bulk-archive --- Archive multiple changes
-   /opsx:explore --- Investigation mode (no implementation)
-   /opsx:onboard --- Guided onboarding through workflow

These commands manage the change lifecycle only.

------------------------------------------------------------------------

## 🧠 /ai-specs:\* --- Governance & Execution Layer

These commands manage standards, documentation, planning, and execution.

-   /ai-specs:init-greenfield\
    Generate backend and frontend standards from templates using your
    tech stack.

-   /ai-specs:update-docs\
    Enforce documentation-standards.mdc (update API spec, data model,
    development guide).

-   /ai-specs:new-us\  
    Create a new structured user story aligned with SDD standards.

-   /ai-specs:enrich-us\
    Improve and refine user stories/tickets for clarity and
    completeness.

-   /ai-specs:handoff-us\
    Prepare a validated user story for implementation (technical-ready state).

-   /ai-specs:plan-backend-ticket\
    Generate an implementation plan for backend tickets.

-   /ai-specs:plan-frontend-ticket\
    Generate an implementation plan for frontend tickets.

-   /ai-specs:commit\  
    Structured commit (and optional PR) workflow with governance checks.

-   /ai-specs:explain\
    Deep conceptual explanation mode.

-   /ai-specs:meta-prompt\
    Improve and structure prompts for better AI execution.

------------------------------------------------------------------------

# 📘 Standards

All authoritative standards live under:

ai-specs/specs/

Standards may initially be empty in greenfield setups.

If backend-standards.mdc or frontend-standards.mdc do not exist, run:

/ai-specs:init-greenfield

This generates deterministic, stack‑specific standards from templates.

------------------------------------------------------------------------

# 📄 Templates

Templates live under:

ai-specs/specs/templates/

Templates define structure only (headings and section order).\
They are never copied verbatim.

Templates prevent:

-   Documentation drift
-   Structural inconsistency
-   AI output randomness

------------------------------------------------------------------------

# ⚡ QuickStart (Greenfield Setup)

1.  Clone the repository

    git clone `<repo>`{=html} cd `<repo>`{=html}

2.  Initialize standards

    /ai-specs:init-greenfield

    Provide:

    -   Backend stack
    -   Database & ORM
    -   API style
    -   Testing stack
    -   Frontend stack
    -   Tooling & CI

3.  Start a change

    /opsx:new

Follow the lifecycle strictly.

------------------------------------------------------------------------

# 🔁 Enhanced Archive Flow

Archive includes:

1.  Artifact verification
2.  Task verification
3.  Spec sync validation
4.  Documentation update
5.  API blocking rule
6.  Archive execution

This ensures no undocumented API changes and no architectural drift.

------------------------------------------------------------------------

# 🎯 Final Principle

Standards first.\
Specs first.\
Code second.

This repository is a controlled development environment, not just a
project scaffold.

------------------------------------------------------------------------

# 🏥 Quermed CRM — Getting Started

This repository hosts the Quermed CRM (FastAPI + React). Full instructions live in
[ai-specs/specs/development_guide.md](ai-specs/specs/development_guide.md); the short version:

```bash
cp .env.example .env            # set JWT_SECRET (>= 32 chars)
docker compose up --build       # db + migrations/seed + backend (8000) + frontend (8080)
docker compose exec -e E2E_ADMIN_PASSWORD='choose-a-long-passphrase' backend python -m app.tooling.e2e_seed
```

Then open http://localhost:8080 and log in with `admin@quermed.com`.

- Backend: `backend/` — `uv sync --all-extras`, `uv run pytest`, `uv run uvicorn app.asgi:app --reload`
- Frontend: `frontend/` — `npm ci`, `npm run dev`, `npm run test:unit`, `npm run test:e2e`
- Contracts: `ai-specs/specs/api-spec.yml` (generated), `ai-specs/specs/data-model.md`
- Standards: `ai-specs/specs/backend-standards.mdc`, `ai-specs/specs/frontend-standards.mdc`, `ai-specs/specs/project-constitution.md`

------------------------------------------------------------------------

# 📜 License

This project is distributed under the terms of the **MIT License**.

Copyright (c) 2026 Jonathan Castro Miguel.

See the [LICENSE](./LICENSE) file for the full license text.
