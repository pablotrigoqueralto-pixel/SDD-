# admin-screens

## Purpose
User and territory management screens for administrators.

## Requirements

### Requirement: User list
`/admin/usuarios` SHALL show users as cards on mobile and a table on desktop (through the shared `DataList`), with search by name/email, filters by role and active state, and a primary action "Nuevo usuario".

#### Scenario: Admin opens list
- **WHEN** an admin opens `/admin/usuarios`
- **THEN** users are listed with name, email, role label in Spanish ("Comercial", "Director/a comercial", "Administración", "Administrador/a"), territories and an "Inactivo" badge when applicable

#### Scenario: Empty search
- **WHEN** the search returns no users
- **THEN** an empty state "No hay usuarios que coincidan" is shown with the "Nuevo usuario" action

### Requirement: User form
`/admin/usuarios/nuevo` and `/admin/usuarios/:id` SHALL present a single form in a mobile bottom sheet / desktop dialog with: nombre completo, email, rol, territorios (multi-select), divisiones (multi-select), contraseña (creation only, or "Restablecer contraseña" on edit), activo (edit only). No other fields.

#### Scenario: Create user
- **WHEN** an admin fills the form and saves
- **THEN** `POST /api/v1/users` is called, a toast "Usuario creado" is shown and the list refreshes

#### Scenario: Validation errors
- **WHEN** the API returns 422 or 409 `email_already_exists`
- **THEN** the error is shown under the email field as "Ya existe un usuario con este email"

#### Scenario: Edit with conflict
- **WHEN** saving returns 409 `conflict`
- **THEN** the shared conflict dialog appears and "Recargar" reloads the user into the form

#### Scenario: Sales rep without scope warning
- **WHEN** role is "Comercial" and no territory or division is selected
- **THEN** an inline warning "Un comercial sin territorio o división no verá ningún centro" is shown but saving is allowed

### Requirement: Territory list and form
`/admin/territorios` SHALL list territories with their provinces and user count; `/admin/territorios/nuevo` and `/admin/territorios/:id` SHALL present a form with nombre and a province picker grouped by autonomous community, showing already-assigned provinces as disabled with the owning territory name.

#### Scenario: Create territory
- **WHEN** an admin names a territory and selects free provinces
- **THEN** `POST /api/v1/territories` is called and the list shows the new territory

#### Scenario: Province taken
- **WHEN** the API returns 409 `province_already_assigned`
- **THEN** the picker highlights the province and shows "Provincia ya asignada a <territorio>"

### Requirement: Admin navigation
`/admin` SHALL show two entries: "Usuarios" and "Territorios". Later changes add more.

#### Scenario: Admin hub
- **WHEN** an admin opens `/admin`
- **THEN** two large tappable cards navigate to the user and territory lists
