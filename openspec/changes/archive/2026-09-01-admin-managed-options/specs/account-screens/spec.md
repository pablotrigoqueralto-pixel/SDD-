# account-screens (delta)

"+ Añadir" beside Cargo and Especialidad in the contact form, and beside Tipo in the account form.

## MODIFIED Requirements

### Requirement: Account form
`/centros/nuevo` and `/centros/:id/editar` SHALL open the account form in `ResponsiveFormContainer`. Above the fold the form SHALL show only Nombre, Tipo and Provincia (required); every other field SHALL sit under a collapsed "Más datos" section (CIF, dirección, código postal, ciudad, teléfonos, email, web, código Sage, divisiones de interés, marcas en uso, datos de facturación y contacto de contabilidad, notas). For an `admin`, Tipo SHALL offer "+ Añadir", which creates an account type — asking for its "compra por licitación" tick — and selects it. Telephone numbers SHALL be edited with the phone list editor. On create the form SHALL show the derived territory and comercial as read-only hints that update when the province changes. Validation messages SHALL be i18n keys resolved in Spanish; backend field errors (`tax_id_invalid`, `tax_id_already_exists` with a link to the existing centre, `postal_code_invalid`, `phone_invalid` pointing at the offending phone row) SHALL render under their field.

#### Scenario: Create in three fields
- **WHEN** a rep fills Nombre, Tipo and Provincia and saves
- **THEN** one `POST /accounts` is sent and the app navigates to `/centros/:id`

#### Scenario: Admin adds a type mid-form
- **WHEN** an admin with Nombre and Provincia already filled opens "+ Añadir" beside Tipo, creates "Consorcio sanitario" ticking "compra por licitación" and saves the dialog
- **THEN** Tipo shows the new type selected, Nombre and Provincia keep their values, and saving the form sends that `account_type_id`

#### Scenario: Duplicate tax id
- **WHEN** the backend answers 409 `tax_id_already_exists`
- **THEN** the CIF field shows "Ya existe un centro con este CIF" with a link to that centre

#### Scenario: Billing note saved
- **WHEN** a user writes the invoicing instructions and the accounting contact in "Datos de facturación" and saves
- **THEN** the text is sent as `billing_notes` and shown in the 360º Facturación section

#### Scenario: Stale edit
- **WHEN** the backend answers 409 `concurrent_modification` on save
- **THEN** the shared conflict dialog opens and offers to reload the account

### Requirement: Contact form
`/centros/:id/contactos/nuevo` and `/centros/:id/contactos/:contactId/editar` SHALL open the contact form with Nombre and Apellidos above the fold; then Cargo (`NativeSelect` from `useJobTitles()`), the "Jefe de servicio" tick (independent of the cargo), **Especialidad** (`NativeSelect` from the specialties catalogue — the medical specialty the person practises, not a commercial division), Email, Teléfonos (phone list editor), Canal preferido (segmented radio: Email / Teléfono, each disabled while its value is empty), Consentimiento comercial (estado + origen; fecha defaults to today when the status changes from "Desconocido"), Contacto principal toggle, Notas. For an `admin`, Cargo and Especialidad SHALL each offer "+ Añadir", which creates the entry and selects it without losing what is already typed. Backend errors (`preferred_channel_missing_value`, `consent_incomplete`, `contact_anonymised`) SHALL render inline.

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

#### Scenario: Admin adds a missing specialty
- **WHEN** an admin filling a contact finds no "Urología", opens "+ Añadir" beside Especialidad, creates it and saves the dialog
- **THEN** Especialidad shows "Urología" selected, Nombre and Apellidos keep their values and saving sends the new `specialty_id`

#### Scenario: A rep sees no add button
- **WHEN** a `sales_rep` opens the contact form
- **THEN** neither Cargo nor Especialidad shows "+ Añadir"
