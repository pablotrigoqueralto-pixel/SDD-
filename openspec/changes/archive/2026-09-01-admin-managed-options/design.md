## Context

Five catalogues sit behind business dropdowns and three of them already have admin creation endpoints (`POST /job-titles`, `POST /loss-reasons`, `POST /product-families`), each following the same shape: a service builds the entity with `next_sort_order()`, the repository `add()`s it and a unique-constraint violation is translated into a `…NameAlreadyExistsError` (409). The other two do not: specialties were deliberately left read-only in change 13, and `account_types` has been seed-only since change 02 — its model has no `add`, no service and no route.

Two facts of the existing code decide most of this design. First, the catalogues carry two kinds of key: a `code` (unique, derived by `slugify_code` for rows created through the API but **hand-written in English for seeded rows** — `management` for "Gerencia") and a unique `name_es`. Neither alone identifies "the option the administrator means", which is why the lookup below uses both. Second, stage reordering is **already implemented end to end** (`PUT /pipelines/{id}/stages/order`, `Pipeline.reorder`, and the "Subir"/"Bajar" buttons on `/admin/pipelines`), so swapping Demo and Presupuesto works today; what is missing is the invariant that keeps `Ganada`, `Perdida` and `En riesgo` at the end.

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**
- A missing option costs one dialog, not an abandoned form: create it and continue with it selected.
- The same name never produces a second entry, whatever the accents or the case.
- Specialties and account types stop needing a deployment to grow.
- A pipeline can be ordered any way that still reads as a pipeline: terminal stages last.

**Non-Goals:** everything in the proposal (renaming/deactivating from the dropdown, new admin screens for specialties and account types, permission changes, merging pre-existing duplicates, drag-and-drop stages).

## Decisions

### D1. "Already exists" becomes reuse-and-reactivate, resolved by `code` **or** by the unaccented name

The create services stop treating an existing name as a conflict. Before inserting they look the catalogue up and, when a row is found, return it — reactivating it first if it was inactive, recording `…​.reactivated` in the audit log so the change is not invisible. The response tells the caller which of the three happened (`created`, `reused`, `reactivated`) so the dialog can say "Ya existía y la hemos reactivado" instead of silently doing something the admin did not ask for.

The lookup matches **either** the `code` the name slugifies to **or** the stored `name_es` compared through `f_unaccent` and case-folded. Both halves are needed, and the reason is in the seed: seeded rows carry English codes chosen by hand (`management` for "Gerencia", `gynaecologist` for "Ginecólogo/a"), so `code` alone would never match the very entries an administrator is most likely to retype, while `name_es` alone would never match an entry created earlier through this same endpoint after its name was edited. Together they cover both origins, and they are a strict superset of what the database enforces (`code` unique, `name_es` CITEXT unique): anything the constraints would reject is caught here first, so the two can never disagree in the direction that matters.

- **Discarded — matching only by `code`**: attempted first and wrong. It looks tidy (the code is what the unique index enforces) but the seeded codes are not derived from their Spanish names, so retyping "Gerencia" would sail past the lookup and then hit the `name_es` unique constraint — a 409 in exactly the case this change exists to remove.
- **Discarded — matching only by `name_es`**: misses entries whose name an administrator later edited, and any future catalogue whose names are not unique.
- **Discarded — keeping the 409 and letting the UI explain it**: the admin is mid-form; answering "ya existe" and leaving them to find it in a list is exactly the interruption this change removes.
- **Discarded — reusing but never reactivating**: the option would be created "successfully" and then not appear in the dropdown, which filters to active entries. A silent no-op is worse than an error.
- **Discarded — this behaviour only in the dropdown, keeping 409 for the admin screens**: two meanings for one endpoint. The rule belongs to the endpoint, and the admin screens gain the same sensible behaviour.

### D1b. Product families are matched inside their division, and only there

`product_families` carries two unique constraints: `name_es` per division and `code` catalogue-wide. Reuse therefore looks **within the requested division**, and a name already used by a family of another division keeps its 409 `product_family_exists`. Reusing across divisions was considered and rejected: it would answer a request for "Dopplers de neurología" with the vascular family, and every product filed under it afterwards would sit in the wrong division — a silent data error in exchange for avoiding one explicit message.

### D2. `POST /api/v1/account-types` carries `buys_via_tender`; specialties carry nothing extra

`account_types.buys_via_tender` is what makes the tender fields appear on an opportunity, so the creation payload asks for it as an explicit boolean (default `false`). Leaving it out would create a type that looks finished and quietly behaves like a private clinic in the one place where it matters.

`AccountType` is currently a frozen entity with no `version` (it is read-only everywhere): creation needs no optimistic locking, so the entity gains a `create()` classmethod and the model gains nothing. Editing an account type stays out of scope, so no version column is added for a feature nobody asked for.

- **Discarded — deriving `buys_via_tender` from the name** ("hospital público" → true): a guess dressed as a rule; the first "Consorcio sanitario" breaks it.
- **Discarded — adding the semantic flags of activity types too**: no dropdown asks for a new activity type, and `counts_as_contact` drives `last_contact_at`. Out of scope.

### D3. One `CreateOptionDialog` on the frontend, five call sites

A single component takes the label, the mutation and the current form value, and gives back the created id. Each form renders it next to its `NativeSelect` behind `useIsAdmin()`. On success it invalidates the reference bundle (or the families/specialties query) and sets the field, so the new option is selected in the form the admin was filling and appears in every other screen at once.

The button is a small "+ Añadir" next to the select, not an option inside it: an `<option>` that is not a value is a trap for screen readers and for anyone using the keyboard, and it breaks the native select on mobile.

- **Discarded — a "＋ Crear…" entry inside the select**: hijacks a value slot, reads as a selectable option to assistive technology and is impossible to style consistently across mobile browsers.
- **Discarded — five bespoke dialogs**: five copies of the same reuse/reactivate messaging, guaranteed to drift.
- **Discarded — free-text with create-on-blur (a combobox)**: every typo becomes a catalogue entry. The explicit button is one extra tap and keeps the catalogue clean.

### D4. Terminal stages are pinned by the domain, not by the screen

`Pipeline.reorder` rejects an order where a stage with `is_won`, `is_lost` or `is_at_risk` precedes an advancing stage, raising the existing `StageOrderInvalidError` (`stage_order_invalid`) — the invariant lives with the entity, so the API, the importer and any future screen inherit it. `/admin/pipelines` then simply disables "Subir"/"Bajar" where the move would be rejected, so the guard is never the way a user discovers the rule.

- **Discarded — enforcing it only in the screen**: an invariant a direct API call can break is not an invariant.
- **Discarded — sorting terminal stages out of the reorder payload**: the endpoint's contract is "every stage id exactly once"; changing that to "some ids" makes the request harder to reason about and breaks the existing round-trip.
- **Discarded — allowing any order (today's behaviour)**: a board whose "Perdida" column sits between Demo and Presupuesto reads as a bug to every user of it.

### D5. Nothing new in the audit vocabulary except reactivation

Creating from a dropdown records exactly the event creating from Administración records (`job_title.created`, `specialty.created`, `account_type.created`, …). Reuse records nothing — nothing changed. Reactivation records `<entity>.reactivated` with `is_active` false → true. An auditor should not be able to tell which screen a legitimate creation came from, only what changed.

## Risks / Trade-offs

- [An admin creates an option that only makes sense for one centre, polluting a global catalogue] → the catalogues are global by design and this change does not alter that; reuse-and-reactivate keeps the growth to genuinely new entries, and Administración can deactivate what stops being used.
- [Reuse hides a typo: the admin types "Ginecologia", gets the existing "Ginecología" and never notices the accent was wrong] → deliberate, and the dialog says which entry it reused. Silently creating the second spelling is the outcome we are preventing.
- [`buys_via_tender` ticked by mistake makes tender fields appear on unrelated opportunities] → the field is optional on the opportunity, the account type is visible in Administración, and the audit log records who created it with which flag.
- [Pinning terminal stages could reject an order an existing deployment already holds] → the seeded pipelines already end with their terminal stages, and the guard only runs on a new reorder; an order already stored is never re-validated.
- [Five forms adopting one dialog is five chances to wire the invalidation wrong] → one component owns the invalidation; the call sites pass a mutation and a setter and are covered by a test each.

## Migration Plan

No migration: no schema change. `AccountType` gains a `create()` classmethod and a repository with `add`/`by_code`/`next_sort_order`; the specialties repository gains the same three. Backend and frontend ship together, `api-spec.yml` is regenerated and `npm run api:types` rerun. Rollback is redeploying the previous image: entries created meanwhile stay, valid and readable, because they are ordinary catalogue rows.

## Open Questions

None — the five catalogues, the admin-only gate, reuse-and-reactivate, the tender flag on new account types, "add only" from the dropdown and terminal stages pinned last were all settled with the user before this design.
