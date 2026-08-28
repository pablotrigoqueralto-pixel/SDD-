## MODIFIED Requirements

### Requirement: Reference data cache
The frontend SHALL load `GET /api/v1/reference-data` once per session through `useReferenceData()` (`staleTime` 5 minutes) and expose selectors `useAccountTypes()`, `useActivityTypes()`, `useDivisions()`, `useBrands()`, `useLossReasons()`, `usePipelines()`, `useJobTitles()`, `useProductFamilies()` that read from the same query. Any admin mutation on a master (job titles and product families included) SHALL invalidate the bundle.

#### Scenario: One request for many consumers
- **WHEN** three components using different selectors mount in the same screen
- **THEN** exactly one request to `/reference-data` is made

#### Scenario: Mutation refreshes consumers
- **WHEN** an admin renames a brand
- **THEN** the bundle query is invalidated and a mounted brand list shows the new name without a page reload

#### Scenario: Job titles from the bundle
- **WHEN** the contact form mounts after the bundle is loaded
- **THEN** the Cargo select is populated without an additional request

#### Scenario: Families from the bundle
- **WHEN** the product form mounts after the bundle is loaded
- **THEN** the Familia select is populated, grouped by division, without an additional request
