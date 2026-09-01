# Tasks — admin-managed-options

scope: backend=true, frontend=true · design-linked: false (AI-designed UI per frontend standards)

## 1. Backend — the shared catalogue rules

- [x] 1.1 [TEST][BE] Write failing tests for reuse-and-reactivate on the job titles endpoint (a name resolving to an existing `code` returns that row with `outcome = "reused"` and creates nothing; an inactive row comes back active with `outcome = "reactivated"` and an audit event; a genuinely new name still answers `created` with `sort_order` last); then implement it in `JobTitleService.create` and expose `outcome` in the response.
- [x] 1.2 [TEST][BE] Write the same failing tests for loss reasons and product families (families match within their division only: the same name in another division creates a new family); then implement both, sharing the resolve-by-code helper rather than copying it three times.
- [x] 1.3 [TEST][BE] Write failing tests for `POST /api/v1/specialties` (admin only, code derived, appended last, the three outcomes, blank name 422); then add `SpecialtyService.create`, the repository writes (`add`, `by_code`, `next_sort_order`) and the route.
- [x] 1.4 [TEST][BE] Write failing tests for `POST /api/v1/account-types` (admin only, `buys_via_tender` explicit and defaulting to false, the three outcomes, the new type usable on an account and present in the bundle with a new ETag); then add the entity `create()`, the repository, the service and the route.

## 2. Backend — pipeline ordering

- [x] 2.1 [TEST][BE] Write failing domain tests for `Pipeline.reorder` (swapping Demo and Presupuesto is accepted; any order placing a stage with `is_won`, `is_lost` or `is_at_risk` before an advancing stage raises `stage_order_invalid` and leaves the stored order untouched); then add the invariant to the entity.
- [x] 2.2 [TEST][BE] Write failing API tests for the guard through `PUT /pipelines/{id}/stages/order` (422 `stage_order_invalid`, no audit event, opportunities keep their stage after a legal swap); then confirm the service surfaces it unchanged.
- [x] 2.3 [BE] Regenerate `api-spec.yml`; update `data-model.md` (which masters administrators may create, the reuse/reactivation rule, terminal stages last) and `development_guide.md` (the seeded-masters table gains the truth for specialties and account types, plus one line on how to swap Demo and Presupuesto).

## 3. Frontend — the shared dialog

- [x] 3.1 [FE] Run `npm run api:types`; add `createSpecialty` and `createAccountType` to the reference feature with their mutations, and the `admin:options` i18n keys (button, dialog title, name label, tender tick, the three outcome messages).
- [x] 3.2 [TEST][FE] Write failing tests for `CreateOptionDialog` (renders only for `admin`; saving selects the new entry and invalidates the reference cache; `reused` and `reactivated` show their message and still select the entry; a 422 stays inside the dialog leaving the field untouched; Escape returns focus to the button); then implement the component in `components/shared/`.
- [x] 3.3 [TEST][FE] Write failing tests for the contact form (Cargo and Especialidad each offer "+ Añadir" for an admin and nothing for a rep; creating mid-form keeps Nombre and Apellidos and sends the new id); then wire both call sites.
- [x] 3.4 [TEST][FE] Write failing tests for the account form (Tipo offers "+ Añadir" with the "compra por licitación" tick, the created type is selected and the rest of the form survives); then wire it.
- [x] 3.5 [TEST][FE] Write failing tests for the product form (Familia creates in the division of the selected family, or asks for the division when none is selected; back office sees no button) and for the lose form (motivo creates a reason that requires neither brand nor note); then wire both.
- [x] 3.6 [TEST][FE] Write failing tests for the pipeline screen (the last advancing stage cannot go down, terminal stages cannot go up, and the swap of Demo and Presupuesto still works); then disable the buttons accordingly.
- [x] 3.7 [FE] Quality gates: `npx tsc --noEmit -p tsconfig.app.json`, eslint, `npx prettier --check --end-of-line auto e2e src`, full Vitest suite green.

## 4. E2E and integration validation

- [x] 4.1 [E2E] Extend Playwright: an admin creates a specialty from the contact form and saves the contact with it; a rep opens the same form and sees no "+ Añadir"; the admin swaps Demo and Presupuesto in `/admin/pipelines` and the board columns follow while an existing opportunity keeps its stage; axe scan mobile and desktop.
- [x] 4.2 [E2E] Full compose smoke plus the complete Playwright suite (desktop + mobile, rate-limit swap, image rebuilt before the run so the suite tests the current bundle).
