## MODIFIED Requirements

### Requirement: Account 360º page
`/centros/:id` SHALL render a header (name, type, city, territory, comercial, "Último contacto", "Próxima actividad", badges) with the sticky actions "Nueva actividad", "Nuevo contacto", "Nueva oportunidad" and "Editar", followed by collapsible sections in this order: Actividades (timeline section: five most recent entries and "Ver todas"), Oportunidades (open opportunities as cards — name, stage badge, amount, days in stage, tender/at-risk badges — with a count of closed ones and "Ver todas" → `/oportunidades?account_id=`; empty state with "Nueva oportunidad"), Presupuestos (the account's current quote versions — display number, estado badge with the expiry visual, total — linking to each quote sheet; quotes are always created from an opportunity, so no direct creation here), Contactos (count), Datos (primary address, additional addresses with "Editar direcciones", CIF, código Sage, teléfono, email, web, divisiones, marcas en uso), Equipos (placeholder with "Disponible en una próxima versión"), Notas. Open/closed state SHALL persist per section in `localStorage`. On desktop (`lg`) the header spans the page and sections are arranged in a 1 + 2 column grid. Contact cards SHALL expose `tel:` and `mailto:` links and a consent badge; managers and admins SHALL see "Reasignar" in the header; managers SHALL see "Anonimizar" on contact cards.

#### Scenario: Placeholders
- **WHEN** the page loads for any account
- **THEN** the section Equipos renders the placeholder text and no request is made for it, while Actividades requests `GET /accounts/{id}/timeline?page_size=5`, Oportunidades requests `GET /accounts/{id}/opportunities` and Presupuestos requests `GET /quotes?account_id={id}&status=all`

#### Scenario: Out of scope
- **WHEN** the backend answers 404 for the account
- **THEN** an `ErrorState` "Centro no encontrado" with a link back to Centros is shown

#### Scenario: Section state remembered
- **WHEN** the user collapses Datos and reopens the page
- **THEN** Datos stays collapsed

#### Scenario: Opportunities section
- **WHEN** the account has two open opportunities and one won
- **THEN** the section shows the two open cards, the text "1 cerrada" and "Ver todas"; tapping a card opens `/oportunidades/:id`

#### Scenario: Quotes section
- **WHEN** the account has quotes across two opportunities
- **THEN** the Presupuestos section lists all their current versions, most recent first, and tapping one opens `/presupuestos/:id`; with no quotes it shows the localized empty state
