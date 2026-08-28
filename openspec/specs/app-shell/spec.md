# app-shell

## Purpose
Frontend shell: login page, authenticated layout, session handling, role-aware routing, i18n, offline banner, conflict dialog, accessibility baseline.

## Requirements

### Requirement: Login page
The frontend SHALL provide `/login` with email and password fields, a single "Entrar" button, Spanish copy, and SHALL be usable on a 375 px viewport with the button visible without scrolling.

#### Scenario: Successful login
- **WHEN** the user submits valid credentials
- **THEN** the access token is kept in memory, the user profile is stored in the session store, and the app navigates to the originally requested URL or `/hoy`

#### Scenario: Invalid credentials
- **WHEN** the API returns 401 `invalid_credentials`
- **THEN** the form shows "Email o contraseña incorrectos" without clearing the email field

#### Scenario: Locked account
- **WHEN** the API returns 401 `account_locked`
- **THEN** the form shows "Cuenta bloqueada temporalmente. Inténtalo en 15 minutos"

### Requirement: Session handling
The frontend SHALL keep the access token only in memory, SHALL call `POST /api/v1/auth/refresh` once on a 401 to obtain a new token and retry the failed request, and SHALL redirect to `/login` when refresh fails.

#### Scenario: Silent refresh
- **WHEN** an API call returns 401 and the refresh cookie is valid
- **THEN** the request is retried with the new token and the user notices nothing

#### Scenario: Reload keeps session
- **WHEN** the user reloads the page with a valid refresh cookie
- **THEN** the app obtains a new access token and renders the requested page without showing the login form

#### Scenario: Logout
- **WHEN** the user taps "Cerrar sesión"
- **THEN** logout is called, the session store is cleared, TanStack Query cache is cleared and the app navigates to `/login`

### Requirement: Authenticated layout
The shell SHALL render, on mobile, a bottom navigation with at most five entries and a sticky page header; on `lg:` and above, a left sidebar with the same entries. The entries are: "Hoy" (`/hoy`, the rep's day: overdue and planned activities with weekly counters), "Centros" (`/centros`), "Pipeline" (`/oportunidades`), "Más" (`/mas`) and, for `admin`, "Administración" (`/admin`). A later change may replace "Más" content with "Buscar" but SHALL NOT exceed five entries.

#### Scenario: Mobile layout
- **WHEN** the viewport is narrower than 1024 px
- **THEN** the bottom navigation is visible, each target is at least 44×44 px, and the current route is highlighted with icon and label

#### Scenario: Desktop layout
- **WHEN** the viewport is 1024 px or wider
- **THEN** the sidebar replaces the bottom navigation and the content area has a max width with the same entries

#### Scenario: Home is the day plan
- **WHEN** an authenticated rep opens `/`
- **THEN** they are redirected to `/hoy` and see their planned and overdue activities instead of a placeholder

#### Scenario: Pipeline entry for every role
- **WHEN** a back office user signs in
- **THEN** the navigation shows Hoy, Centros, Pipeline and Más (four entries); an admin sees five

### Requirement: Role-aware routing
Routes SHALL be wrapped by an auth guard; role-gated routes SHALL render a "Sin permiso" page for other roles.

#### Scenario: Unauthenticated deep link
- **WHEN** an anonymous user opens `/admin/usuarios`
- **THEN** the app redirects to `/login?next=/admin/usuarios` and returns there after login

#### Scenario: Sales rep opens admin
- **WHEN** a `sales_rep` opens `/admin/usuarios`
- **THEN** the "Sin permiso" page is shown and the admin entry is absent from navigation

### Requirement: Internationalisation bundle
All user-visible strings SHALL come from `src/i18n/es-ES/*.json` through `t()`; the lint rule `react/jsx-no-literals` SHALL fail on literal JSX text in `src/features` and `src/components`.

#### Scenario: Missing key visible in dev
- **WHEN** a key is missing from the bundle
- **THEN** the key itself is rendered and a console warning is logged in development

### Requirement: Design tokens and primitives
The shell SHALL define Quermed design tokens (colours, radius, spacing, typography) as CSS variables mapped in Tailwind and SHALL include the shadcn/ui primitives Button, Input, Label, Form, Select, Sheet, Dialog, Toast, Skeleton, Badge, Accordion, Command.

#### Scenario: Contrast baseline
- **WHEN** the token palette is audited
- **THEN** text on background pairs used by primitives meet 4.5:1 and UI components 3:1

### Requirement: Offline banner
The shell SHALL show a persistent banner "Sin conexión. Los datos mostrados pueden no estar actualizados" when the browser reports offline and hide it on reconnection.

#### Scenario: Going offline
- **WHEN** `navigator.onLine` becomes false
- **THEN** the banner appears within one second and cached pages remain readable

### Requirement: Conflict dialog
The shell SHALL provide a shared dialog for 409 `conflict` responses with the text "Otro usuario ha modificado este registro" and a "Recargar" action that refetches the resource.

#### Scenario: Stale edit
- **WHEN** a mutation returns 409 `conflict`
- **THEN** the dialog opens, and "Recargar" invalidates the resource query and closes the dialog

### Requirement: Error mapping
Problem responses SHALL be normalised to a `Problem` object; field errors SHALL be applied to the corresponding form fields; unknown codes SHALL show a generic toast "Ha ocurrido un error. Inténtalo de nuevo".

#### Scenario: Field error mapping
- **WHEN** a 422 arrives with `errors[]` for `email`
- **THEN** the email field shows the translated message for its `code`

### Requirement: Accessibility baseline
Every page in this change SHALL pass axe with zero serious/critical violations on desktop and mobile Playwright projects and SHALL be operable by keyboard.

#### Scenario: Keyboard login
- **WHEN** a user tabs through the login page
- **THEN** focus order is email → password → "Entrar", the focus ring is visible, and Enter submits
