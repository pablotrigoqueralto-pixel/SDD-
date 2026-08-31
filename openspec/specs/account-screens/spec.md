# account-screens

## Purpose
Mobile-first screens for accounts and contacts: list with filters, three-field account form, 360º account page with collapsible sections, contact form, job titles administration and navigation.

## Requirements

### Requirement: Account list page
The frontend SHALL provide `/centros` ("Centros") for every role, rendering `DataList` (cards below `lg`, table from `lg`) with name, type, city, comercial and badges "Inactivo" / "Territorio distinto". It SHALL offer a debounced search box (300 ms, `q`) and filters (tipo, territorio, comercial, división, sin comercial, mostrar inactivos) shown inline on desktop and inside a "Filtros" sheet on mobile; filters and search SHALL be reflected in the URL query string. Mobile SHALL load more pages with a "Cargar más" button; desktop SHALL paginate. A "Nuevo centro" primary action SHALL always be reachable.

#### Scenario: Search persists in URL
- **WHEN** the user types "tambre" and selects territory "Centro"
- **THEN** the list requests `/accounts?q=tambre&territory_id=…` and the URL contains both parameters so the browser back button restores them

#### Scenario: Empty result
- **WHEN** no account matches
- **THEN** an `EmptyState` with the action "Nuevo centro" is shown

### Requirement: Account form
`/centros/nuevo` and `/centros/:id/editar` SHALL open the account form in `ResponsiveFormContainer`. Above the fold the form SHALL show only Nombre, Tipo and Provincia (required); every other field SHALL sit under a collapsed "Más datos" section (CIF, dirección, código postal, ciudad, teléfonos, email, web, código Sage, divisiones de interés, marcas en uso, datos de facturación y contacto de contabilidad, notas). Telephone numbers SHALL be edited with the phone list editor. On create the form SHALL show the derived territory and comercial as read-only hints that update when the province changes. Validation messages SHALL be i18n keys resolved in Spanish; backend field errors (`tax_id_invalid`, `tax_id_already_exists` with a link to the existing centre, `postal_code_invalid`, `phone_invalid` pointing at the offending phone row) SHALL render under their field.

#### Scenario: Create in three fields
- **WHEN** a rep fills Nombre, Tipo and Provincia and saves
- **THEN** one `POST /accounts` is sent and the app navigates to `/centros/:id`

#### Scenario: Duplicate tax id
- **WHEN** the backend answers 409 `tax_id_already_exists`
- **THEN** the CIF field shows "Ya existe un centro con este CIF" with a link to that centre

#### Scenario: Billing note saved
- **WHEN** a user writes the invoicing instructions and the accounting contact in "Datos de facturación" and saves
- **THEN** the text is sent as `billing_notes` and shown in the 360º Facturación section

#### Scenario: Stale edit
- **WHEN** the backend answers 409 `concurrent_modification` on save
- **THEN** the shared conflict dialog opens and offers to reload the account

### Requirement: Account 360º page
`/centros/:id` SHALL render a header (name, type, city, territory, comercial, "Último contacto", "Próxima actividad", badges) with the sticky actions "Nueva actividad", "Nuevo contacto", "Nueva oportunidad" and "Editar", followed by collapsible sections in this order: Actividades (timeline section: five most recent entries and "Ver todas"), Oportunidades (open opportunities as cards — name, stage badge, amount, days in stage, tender/at-risk badges — with a count of closed ones and "Ver todas" → `/oportunidades?account_id=`; empty state with "Nueva oportunidad"), Presupuestos (the account's current quote versions — display number, estado badge with the expiry visual, total — linking to each quote sheet; quotes are always created from an opportunity, so no direct creation here), Contactos (count), Datos (primary address, additional addresses with "Editar direcciones", CIF, código Sage, the full phone list with each label and `tel:` link, email, web, divisiones, marcas en uso), Facturación (the `billing_notes` text, or its empty state), Equipos (placeholder with "Disponible en una próxima versión"), Notas. Open/closed state SHALL persist per section in `localStorage`. On desktop (`lg`) the header spans the page and sections are arranged in a 1 + 2 column grid. Contact cards SHALL expose `tel:` (primary phone) and `mailto:` links, a consent badge and, when set, a "Jefe de servicio" badge; managers and admins SHALL see "Reasignar" in the header; managers SHALL see "Anonimizar" on contact cards.

#### Scenario: Placeholders
- **WHEN** the page loads for any account
- **THEN** the section Equipos renders the placeholder text and no request is made for it, while Actividades requests `GET /accounts/{id}/timeline?page_size=5`, Oportunidades requests `GET /accounts/{id}/opportunities` and Presupuestos requests `GET /quotes?account_id={id}&status=all`

#### Scenario: Out of scope
- **WHEN** the backend answers 404 for the account
- **THEN** an `ErrorState` "Centro no encontrado" with a link back to Centros is shown

#### Scenario: Section state remembered
- **WHEN** the user collapses Datos and reopens the page
- **THEN** Datos stays collapsed

#### Scenario: Phones with labels
- **WHEN** the centre has three labelled phones
- **THEN** Datos lists the three with their labels, each number a `tel:` link, the primary one first and extensions rendered with the number

#### Scenario: Opportunities section
- **WHEN** the account has two open opportunities and one won
- **THEN** the section shows the two open cards, the text "1 cerrada" and "Ver todas"; tapping a card opens `/oportunidades/:id`

#### Scenario: Quotes section
- **WHEN** the account has quotes across two opportunities
- **THEN** the Presupuestos section lists all their current versions, most recent first, and tapping one opens `/presupuestos/:id`; with no quotes it shows the localized empty state

### Requirement: Assignment and addresses dialogs
"Reasignar" SHALL open a small form (comercial from active reps, territorio from active territories) calling `PUT /accounts/{id}/assignment`; "Editar direcciones" SHALL open a form managing the labelled address list (add/remove rows, max 10) calling `PUT /accounts/{id}/addresses`. Both SHALL send `If-Match` and refresh the account query on success.

#### Scenario: Reassign owner
- **WHEN** a manager picks another rep and saves
- **THEN** the header shows the new comercial without a page reload

### Requirement: Contact form
`/centros/:id/contactos/nuevo` and `/centros/:id/contactos/:contactId/editar` SHALL open the contact form with Nombre and Apellidos above the fold; then Cargo (`NativeSelect` from `useJobTitles()`), the "Jefe de servicio" tick (independent of the cargo), Especialidad (division select, defaulted to the account's only division of interest when it has exactly one), Email, Teléfonos (phone list editor), Canal preferido (segmented radio: Email / Teléfono, each disabled while its value is empty), Consentimiento comercial (estado + origen; fecha defaults to today when the status changes from "Desconocido"), Contacto principal toggle, Notas. Backend errors (`preferred_channel_missing_value`, `consent_incomplete`, `contact_anonymised`) SHALL render inline.

#### Scenario: Consent date default
- **WHEN** the user changes consent status to "Concedido"
- **THEN** the date field is filled with today's date and origin becomes required

#### Scenario: Create contact
- **WHEN** the user fills Nombre and Apellidos and saves
- **THEN** one `POST /accounts/{id}/contacts` is sent, the form closes and the Contactos section shows the new card

#### Scenario: Surgeon and head of department
- **WHEN** the user picks the cargo "Cirujano/a vascular" and ticks "Jefe de servicio"
- **THEN** both travel in the payload and the contact card shows the cargo plus a "Jefe de servicio" badge

### Requirement: Job titles admin screen
The admin hub SHALL gain a "Cargos" card leading to `/admin/cargos`, a list + form screen cloned from loss reasons (create, rename, activate/deactivate with `If-Match`), restricted to `admin`.

#### Scenario: Rename a title
- **WHEN** an admin renames "Compras / suministros" to "Compras"
- **THEN** `PATCH /job-titles/{id}` is sent with `If-Match` and the reference bundle is invalidated

### Requirement: Navigation
The bottom navigation SHALL show Hoy · Centros · Más, the sidebar SHALL add "Centros", and admin entries SHALL remain under Más / the sidebar admin group.

#### Scenario: Mobile navigation
- **WHEN** a rep taps "Centros" in the bottom bar on a 412 px viewport
- **THEN** `/centros` opens and the tab is marked current

### Requirement: Spanish copy and accessibility
All copy SHALL come from the `accounts` and `contacts` i18n namespaces using product vocabulary (Centro, Contacto, Comercial, Territorio, Cargo); the list, form, 360º page and contact form SHALL pass axe on mobile and desktop and be operable by keyboard (collapsible sections are buttons with `aria-expanded`).

#### Scenario: No literal copy
- **WHEN** ESLint runs
- **THEN** no `jsx-no-literals` violation exists in `features/accounts` or `features/contacts`

### Requirement: Phone list editor
A shared phone list editor SHALL be used by the account and contact forms. Each row SHALL offer Etiqueta (text input with a datalist of suggestions — Principal, Secretaría, Servicio, Consulta, Despacho, Extensión, Móvil, Fax — accepting any typed value), Número, Extensión (optional) and Nota (optional), plus per-row "Quitar" and "Hacer principal" actions and an "Añadir teléfono" button. Rows SHALL stack vertically on mobile and place label and number side by side from `lg:`. The list SHALL be keyboard-operable and every control labelled; the editor SHALL pass axe in both viewports.

#### Scenario: Add and promote
- **WHEN** the user adds "Secretaría" with a number and taps "Hacer principal" on it
- **THEN** that row moves to the top and is sent first in the `phones` array

#### Scenario: Remove a row
- **WHEN** the user taps "Quitar" on the second phone and saves
- **THEN** the payload carries the remaining phones only

#### Scenario: Free label accepted
- **WHEN** the user types a label that is not in the suggestion list
- **THEN** it is accepted verbatim and saved
