## MODIFIED Requirements

### Requirement: Admin navigation
`/admin` SHALL show five entries: "Usuarios", "Territorios", "Marcas", "Motivos de pérdida" and "Pipelines". Later changes add more.

#### Scenario: Admin hub
- **WHEN** an admin opens `/admin`
- **THEN** five large tappable cards navigate to the user, territory, brand, loss reason and pipeline screens, laid out in one column on mobile and two columns from the `sm` breakpoint
