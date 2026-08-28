## MODIFIED Requirements

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
