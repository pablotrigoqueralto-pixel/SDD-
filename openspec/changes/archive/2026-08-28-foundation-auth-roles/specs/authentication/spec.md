## ADDED Requirements

### Requirement: Password login
The system SHALL authenticate an active user by email and password at `POST /api/v1/auth/login` and, on success, return a short-lived access token in the response body and set a rotating refresh token as an `HttpOnly; Secure; SameSite=Strict` cookie.

Required fields: `email` (identifies the user), `password` (proves identity). No other fields.

#### Scenario: Valid credentials
- **WHEN** an active user posts a correct email and password
- **THEN** the response is 200 with `{ "access_token", "token_type": "bearer", "expires_in": 900, "user": <UserRead> }` and a `refresh_token` cookie scoped to `/api/v1/auth`

#### Scenario: Invalid credentials
- **WHEN** the email does not exist or the password is wrong
- **THEN** the response is 401 with problem code `invalid_credentials`, the message does not reveal which part failed, and the failed attempt is counted for that email

#### Scenario: Inactive user
- **WHEN** a deactivated user posts correct credentials
- **THEN** the response is 401 with code `invalid_credentials` (indistinguishable from wrong credentials)

#### Scenario: Password stored securely
- **WHEN** a password is persisted
- **THEN** only an argon2id hash is stored; the plaintext never appears in logs or the database

### Requirement: Account lockout
The system SHALL lock an account for 15 minutes after 10 consecutive failed login attempts and SHALL reset the counter on a successful login.

#### Scenario: Tenth failure locks the account
- **WHEN** the tenth consecutive failed attempt for an email occurs
- **THEN** the response is 401 with code `account_locked`, and subsequent attempts with the correct password also return `account_locked` until 15 minutes elapse

#### Scenario: Counter resets
- **WHEN** a user logs in successfully after fewer than 10 failures
- **THEN** the failure counter for that email is set to zero

### Requirement: Rate limiting on auth endpoints
Endpoints under `/api/v1/auth/*` SHALL be limited to 10 requests per minute per client IP.

#### Scenario: Limit exceeded
- **WHEN** an IP sends an eleventh request to `/api/v1/auth/login` within one minute
- **THEN** the response is 429 with code `rate_limited` and a `Retry-After` header

### Requirement: Access token
Access tokens SHALL be JWTs signed with the server secret, valid for 15 minutes, carrying `sub` (user id), `role` and `exp`. Protected endpoints SHALL require `Authorization: Bearer <token>`.

#### Scenario: Missing or expired token
- **WHEN** a protected endpoint is called without a token or with an expired/invalid one
- **THEN** the response is 401 with code `unauthenticated`

#### Scenario: Token for deactivated user
- **WHEN** a still-valid access token belongs to a user deactivated after issuance
- **THEN** the response is 401 with code `unauthenticated`

### Requirement: Refresh token rotation
`POST /api/v1/auth/refresh` SHALL exchange a valid refresh cookie for a new access token and a new refresh token, invalidating the previous refresh token. Refresh tokens SHALL be stored hashed, expire after 30 days, and be revocable.

#### Scenario: Successful refresh
- **WHEN** the client calls refresh with a valid, unused refresh cookie
- **THEN** the response is 200 with a new access token and a new refresh cookie, and the old refresh token is marked used

#### Scenario: Reuse of a rotated token
- **WHEN** a refresh token that was already rotated is presented again
- **THEN** the response is 401 with code `unauthenticated` and all refresh tokens of that user are revoked (token theft assumption)

#### Scenario: Expired refresh token
- **WHEN** the refresh token is older than 30 days
- **THEN** the response is 401 with code `unauthenticated`

### Requirement: Logout
`POST /api/v1/auth/logout` SHALL revoke the presented refresh token and clear the cookie.

#### Scenario: Logout
- **WHEN** an authenticated client calls logout
- **THEN** the response is 204, the refresh cookie is cleared, and a later refresh with that token returns 401

### Requirement: Password change
`POST /api/v1/auth/password` SHALL allow an authenticated user to change their own password by providing the current password and a new one of at least 12 characters, and SHALL revoke all other refresh tokens of the user.

Required fields: `current_password` (prevents change on a stolen session), `new_password` (the new secret).

#### Scenario: Successful change
- **WHEN** the current password is correct and the new password has ≥ 12 characters
- **THEN** the response is 204, the new hash is stored, other sessions' refresh tokens are revoked, and an audit event `user.password_changed` is recorded without any password material

#### Scenario: Wrong current password
- **WHEN** the current password is incorrect
- **THEN** the response is 400 with code `invalid_current_password`

#### Scenario: Weak new password
- **WHEN** the new password has fewer than 12 characters
- **THEN** the response is 422 with a field error on `new_password` and code `password_too_short`

### Requirement: Authentication provider abstraction
Credential verification SHALL be implemented behind an `AuthProvider` protocol with a `PasswordAuthProvider` implementation, and the `User` model SHALL carry nullable `identity_provider` and `external_id` columns so an OIDC provider can be added without changing the login API shape.

#### Scenario: Provider swap does not change routers
- **WHEN** a second `AuthProvider` implementation is registered in dependency injection
- **THEN** no changes are required in `app/api/v1/auth.py` for login, refresh or logout
