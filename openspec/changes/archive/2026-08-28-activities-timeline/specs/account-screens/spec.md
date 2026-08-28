## MODIFIED Requirements

### Requirement: Account 360º page
`/centros/:id` SHALL render a header (name, type, city, territory, comercial, "Último contacto", "Próxima actividad", badges) with the sticky actions "Nueva actividad", "Nuevo contacto" and "Editar", followed by collapsible sections in this order: Actividades (timeline section: five most recent entries and "Ver todas"), Contactos (count), Datos (primary address, additional addresses with "Editar direcciones", CIF, código Sage, teléfono, email, web, divisiones, marcas en uso), Oportunidades, Presupuestos, Equipos (placeholders with "Disponible en una próxima versión"), Notas. Open/closed state SHALL persist per section in `localStorage`. On desktop (`lg`) the header spans the page and sections are arranged in a 1 + 2 column grid. Contact cards SHALL expose `tel:` and `mailto:` links and a consent badge; managers and admins SHALL see "Reasignar" in the header; managers SHALL see "Anonimizar" on contact cards.

#### Scenario: Placeholders
- **WHEN** the page loads for any account
- **THEN** the sections Oportunidades, Presupuestos and Equipos render the placeholder text and no request is made for them, while Actividades requests `GET /accounts/{id}/timeline?page_size=5`

#### Scenario: Out of scope
- **WHEN** the backend answers 404 for the account
- **THEN** an `ErrorState` "Centro no encontrado" with a link back to Centros is shown

#### Scenario: Section state remembered
- **WHEN** the user collapses Datos and reopens the page
- **THEN** Datos stays collapsed
