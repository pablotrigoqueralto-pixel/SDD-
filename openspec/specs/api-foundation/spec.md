# api-foundation

## Purpose
Versioned API conventions: problem+json errors, pagination, optimistic locking, health endpoints, OpenAPI export, structured logging.

## Requirements

### Requirement: Versioned base path
All business endpoints SHALL be served under `/api/v1`. Health endpoints SHALL be served at `/health` and `/health/ready` without authentication.

#### Scenario: Liveness
- **WHEN** `GET /health` is called
- **THEN** the response is 200 `{ "status": "ok" }` without touching the database

#### Scenario: Readiness with database down
- **WHEN** `GET /health/ready` is called and the database is unreachable
- **THEN** the response is 503 `{ "status": "degraded", "database": "unavailable" }`

### Requirement: Problem details error format
Every error response SHALL be `application/problem+json` with `type`, `title`, `status`, `detail`, `code`, `trace_id`, and, for validation errors, `errors[]` of `{ field, message, code }`.

#### Scenario: Request validation error
- **WHEN** a request body fails schema validation
- **THEN** the response is 422 with `code: "validation_error"` and one `errors[]` entry per invalid field using dotted paths

#### Scenario: Unexpected exception
- **WHEN** an unhandled exception occurs
- **THEN** the response is 500 with `code: "internal_error"`, a `trace_id`, no stack trace, and the exception is logged with the same `trace_id`

#### Scenario: Trace id propagation
- **WHEN** a request carries `X-Request-ID`
- **THEN** the same value is used as `trace_id` in logs and error bodies and echoed back in the `X-Request-ID` response header

### Requirement: Pagination envelope
Every list endpoint SHALL accept `page` (≥ 1, default 1) and `page_size` (1–200, default 50) and return `{ items, total, page, page_size }`. Sorting SHALL use `sort=<field>` or `sort=-<field>` with a comma-separated list, restricted to fields declared per endpoint.

#### Scenario: Page size over limit
- **WHEN** `page_size=500` is requested
- **THEN** the response is 422 with a field error on `page_size`

#### Scenario: Unknown sort field
- **WHEN** `sort=foo` is requested on an endpoint that does not declare `foo`
- **THEN** the response is 422 with code `invalid_sort_field`

### Requirement: Optimistic locking
Every mutable resource SHALL expose `version`. `PATCH`/`PUT` on such resources SHALL require `If-Match: "<version>"` and SHALL return 409 `conflict` when it does not match and 428 `precondition_required` when absent.

#### Scenario: Missing If-Match
- **WHEN** a `PATCH` is sent without `If-Match`
- **THEN** the response is 428 with code `precondition_required`

#### Scenario: Concurrent edit
- **WHEN** two clients read version 3 and both patch; the second uses `If-Match: "3"` after the first succeeded
- **THEN** the second receives 409 with code `conflict` and the resource is at version 4 with only the first change applied

### Requirement: Security headers and CORS
Responses SHALL include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`; CORS SHALL allow only origins from `CORS_ORIGINS` with credentials.

#### Scenario: Disallowed origin
- **WHEN** a browser preflight comes from an origin not in `CORS_ORIGINS`
- **THEN** no `Access-Control-Allow-Origin` header is returned

### Requirement: OpenAPI export
The backend SHALL generate OpenAPI 3.1 and `make openapi` SHALL write it to `ai-specs/specs/api-spec.yml`; CI SHALL fail if the committed file is stale.

#### Scenario: Stale spec detected
- **WHEN** a router changes and `api-spec.yml` is not regenerated
- **THEN** the backend CI job fails with a diff

### Requirement: Structured logging
Logs SHALL be structured (JSON outside dev) and include `trace_id`, `user_id` (when authenticated), `method`, `path`, `status`, `duration_ms` per request; personal data (names, emails, phones) SHALL never be logged.

#### Scenario: Request log line
- **WHEN** any request completes
- **THEN** one `request_completed` log event is emitted with the fields above and no email or name values
