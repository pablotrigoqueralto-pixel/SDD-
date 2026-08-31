# app-shell (delta)

Más gains a highlighted "Informes" card for every role; the five navigation entries stay untouched.

## MODIFIED Requirements

### Requirement: Authenticated layout
The shell SHALL render, on mobile, a bottom navigation with at most five entries and a sticky page header; on `lg:` and above, a left sidebar with the same entries. The entries are, for every role: "Hoy" (`/hoy`, the rep's day: overdue and planned activities with weekly counters), "Centros" (`/centros`), "Pipeline" (`/oportunidades`), "Buscar" (`/buscar`) and "Más" (`/mas`). "Administración" (`/admin`) SHALL no longer occupy a bar slot: for `admin` it SHALL be the first card inside Más. Más SHALL also carry an "Informes" card (`/informes`) for every role — first card for `sales_rep`, `sales_manager` and `back_office`, and immediately after "Administración" for `admin` — plus the import entries for `back_office` and `admin`.

#### Scenario: Mobile layout
- **WHEN** the viewport is narrower than 1024 px
- **THEN** the bottom navigation is visible, each target is at least 44×44 px, and the current route is highlighted with icon and label

#### Scenario: Desktop layout
- **WHEN** the viewport is 1024 px or wider
- **THEN** the sidebar replaces the bottom navigation and the content area has a max width with the same entries

#### Scenario: Home is the day plan
- **WHEN** an authenticated rep opens `/`
- **THEN** they are redirected to `/hoy` and see their planned and overdue activities instead of a placeholder

#### Scenario: Five entries for every role
- **WHEN** any user signs in
- **THEN** the navigation shows Hoy, Centros, Pipeline, Buscar and Más; an admin additionally finds "Administración" as the first card inside Más

#### Scenario: Informes reachable from Más
- **WHEN** any authenticated user opens Más
- **THEN** an "Informes" card is present and navigates to `/informes` (first card, except for `admin` where it follows "Administración")
