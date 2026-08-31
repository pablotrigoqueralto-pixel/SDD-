# account-screens (delta)

The contacts page with cumulative filters, the specialty select in the contact form and the centre's derived specialties.

## MODIFIED Requirements

### Requirement: Contact form
`/centros/:id/contactos/nuevo` and `/centros/:id/contactos/:contactId/editar` SHALL open the contact form with Nombre and Apellidos above the fold; then Cargo (`NativeSelect` from `useJobTitles()`), the "Jefe de servicio" tick (independent of the cargo), **Especialidad** (`NativeSelect` from the specialties catalogue — the medical specialty the person practises, not a commercial division), Email, Teléfonos (phone list editor), Canal preferido (segmented radio: Email / Teléfono, each disabled while its value is empty), Consentimiento comercial (estado + origen; fecha defaults to today when the status changes from "Desconocido"), Contacto principal toggle, Notas. Backend errors (`preferred_channel_missing_value`, `consent_incomplete`, `contact_anonymised`) SHALL render inline.

#### Scenario: Consent date default
- **WHEN** the user changes consent status to "Concedido"
- **THEN** the date field is filled with today's date and origin becomes required

#### Scenario: Create contact
- **WHEN** the user fills Nombre and Apellidos and saves
- **THEN** one `POST /accounts/{id}/contacts` is sent, the form closes and the Contactos section shows the new card

#### Scenario: Surgeon and head of department
- **WHEN** the user picks the cargo "Cirujano/a vascular" and ticks "Jefe de servicio"
- **THEN** both travel in the payload and the contact card shows the cargo plus a "Jefe de servicio" badge

#### Scenario: Specialty offered from the catalogue
- **WHEN** the user opens the Especialidad selector
- **THEN** it lists the active specialties in catalogue order, no commercial divisions appear, and saving sends `specialty_id`

## ADDED Requirements

### Requirement: Contacts page
`/contactos` SHALL be reachable by every authenticated role from a "Contactos" card in Más, and SHALL list every contact visible to the user via `GET /contacts`. On mobile it SHALL render cards (name, specialty, cargo, centre, "Jefe de servicio" badge when set, tap-to-call on the primary phone) with "Cargar más"; from `lg:` a paginated table with columns Nombre, Especialidad, Cargo, Centro and Teléfono. Tapping a row SHALL open that contact's centre. Back office SHALL see the list without contact actions, as elsewhere.

#### Scenario: Rep opens the page
- **WHEN** a `sales_rep` opens `/contactos`
- **THEN** only contacts of centres in their scope are listed and one request is made

#### Scenario: Row opens the centre
- **WHEN** the user taps a contact row
- **THEN** the app navigates to that contact's account page

#### Scenario: Empty state
- **WHEN** the filters leave no results
- **THEN** a neutral empty state is shown with an action to clear the filters

### Requirement: Cumulative filters with chips
The contacts page SHALL offer a search box and filters for Especialidad (multiple), Centro (multiple), Cargo and "Jefe de servicio", opened from a sheet on mobile and inline from `lg:`. Every active filter SHALL render as a chip with an × that removes only that value, plus "Quitar filtros" when more than one is active. The filter state SHALL live in the URL query string, so reloading or sharing the address reproduces the same list.

#### Scenario: Two specialties add up
- **WHEN** the user picks "Cardiología" and "Neurología"
- **THEN** two chips appear, the list shows contacts of either specialty and the URL carries both values

#### Scenario: Narrow by centre
- **WHEN** the user adds a centre to those two specialties
- **THEN** the list narrows to that centre's contacts of either specialty

#### Scenario: Remove one chip
- **WHEN** the user taps the × of one specialty chip
- **THEN** only that value is removed, the other filters stay and the URL updates

#### Scenario: Shared URL reproduces the list
- **WHEN** a URL carrying two specialties and one centre is opened directly
- **THEN** the same filters are active and the same contacts are listed

### Requirement: Specialties on the account 360º
The account page SHALL show the distinct specialties of its contacts as read-only badges in the Contactos section, derived from the contacts already loaded — never a field to maintain. With no contacts carrying a specialty the badges SHALL be absent, without an empty placeholder.

#### Scenario: Derived badges
- **WHEN** a centre has a cardiologist and two neurologists
- **THEN** the Contactos section shows the badges "Cardiología" and "Neurología" once each

#### Scenario: Nothing to derive
- **WHEN** no contact of the centre has a specialty
- **THEN** no specialty badges are rendered
