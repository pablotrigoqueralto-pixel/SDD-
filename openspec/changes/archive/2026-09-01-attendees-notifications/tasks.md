# Tasks — attendees-notifications

scope: backend=true, frontend=true · design-linked: false (AI-designed UI per frontend standards)

## 1. Backend — attendees on activities

- [x] 1.1 [TEST][BE] Write failing domain tests for attendees on `Activity` (several are kept, replaced wholesale on save, the owner among them raises `owner_cannot_attend`, an inactive user raises `attendee_not_active`); then add the field and its invariants to the entity.
- [x] 1.2 [TEST][BE] Write failing migration tests for `0011` (both `activity_attendees` and `notifications` exist with their indexes, cascading from the activity, and the downgrade drops them); then write the revision.
- [x] 1.3 [TEST][BE] Write failing repository tests (attendees load with the activity, delete-and-reinsert on save persists them, `add()` writes them too — the trap change 12 fell into); then extend the model, the repository and the mapping.
- [x] 1.4 [TEST][BE] Write failing API tests for `attendee_ids` in create/update payloads (returned as `attendees[]`, an attendee who cannot see the centre gives 422 `attendee_out_of_scope`, an attendee still cannot complete or reschedule); then wire the service validation and the schemas.

## 2. Backend — notifications

- [x] 2.1 [TEST][BE] Write failing tests for the notification collector (a notice is committed with the change that caused it, a rolled-back write leaves none, `user_id == actor_id` is a no-op); then add the domain entity, the `NotificationCollector` on the unit of work and its fake.
- [x] 2.2 [TEST][BE] Write failing tests for the repository and the model (unread by user newest first, marking one and marking all, a read notice stays in the table); then add `NotificationModel` and the SQLAlchemy repository.
- [x] 2.3 [TEST][BE] Write failing API tests for `GET /api/v1/notifications` (own only — a `user_id` parameter is ignored for every role including admin, unread only, cap of 20 with a truthful `unread_count`); then add the query, the schema and the route.
- [x] 2.4 [TEST][BE] Write failing API tests for marking read (one, all, already-read is idempotent, someone else's notice is 404 not 403); then add both endpoints.
- [x] 2.5 [TEST][BE] Write failing tests for the four events (attendee added → `activity_attending`; activity created or reassigned for someone else → `activity_assigned`; account assigned → `account_assigned`; opportunity reassigned → `opportunity_assigned`; each with the payload snapshot, and none of them when the actor is the recipient); then emit them from the activity, account and opportunity services.

## 3. Backend — calendar range and docs

- [x] 3.1 [TEST][BE] Write failing tests for `from`/`to` on the calendar feed (an inclusive range returns its activities, `year`+`month`+`from` together is 422, over 92 days is 422 `range_too_long`, role scoping unchanged); then extend the query and the route.
- [x] 3.2 [TEST][BE] Write failing tests for "owned or attended" in `TodayQueries.for_user` and the calendar (an attended activity appears with `is_attendee = true`, the weekly counters do NOT count it, a rep's month includes what they attend); then widen both predicates.
- [x] 3.3 [BE] Regenerate `api-spec.yml`; update `data-model.md` (both tables, the notification kinds and payload rule, the attendee invariants) and `development_guide.md` (what notifies and what does not, the invited rule, the Listado view).

## 4. Frontend — attendees and the invited badge

- [x] 4.1 [FE] Run `npm run api:types`; add the notifications feature skeleton (api, queries with refetch-on-focus, keys) and the `activities`/`common` i18n keys for acompañantes, Invitado, the notification lines and the Listado filters.
- [x] 4.2 [TEST][FE] Write failing tests for the activity form (Acompañantes lists active colleagues without the owner, ticking one sends `attendee_ids`, `attendee_out_of_scope` renders inline); then add the field.
- [x] 4.3 [TEST][FE] Write failing tests for the invited card on Hoy and in the month day list (badge shown, "Hecha" and "Reprogramar" absent, tapping opens the activity); then render the badge and hide the actions.

## 5. Frontend — notifications

- [x] 5.1 [TEST][FE] Write failing tests for the bell (count in the accessible name, no badge when empty, navigates to `/hoy`, refetches on focus); then add it to the header.
- [x] 5.2 [TEST][FE] Write failing tests for the block on Hoy (renders above Atrasadas, one row per notice with actor and subject, opening marks read and navigates, "Marcar todo como leído" empties it, nothing rendered when empty); then implement the block.

## 6. Frontend — the Listado view

- [x] 6.1 [TEST][FE] Write failing tests for the third segment (Día / Mes / Listado switch without a route change, one request per view); then extend the switcher.
- [x] 6.2 [TEST][FE] Write failing tests for the range list (Desde/Hasta defaulting to the current month, rep selector only for staff, cards on mobile and table from `lg:`, a too-long range shows the backend message, empty range shows the empty state); then implement the view.
- [x] 6.3 [FE] Quality gates: `npx tsc --noEmit -p tsconfig.app.json`, eslint, `npx prettier --check --end-of-line auto e2e src`, full Vitest suite green.

## 7. E2E and integration validation

- [x] 7.1 [E2E] Extend Playwright: a manager creates an activity for a rep and adds a second rep as attendee; the owner sees it as theirs and the attendee sees it with the Invitado badge and no actions; both find the notice on Hoy, one opens it and the other marks all read; axe scan mobile and desktop.
- [x] 7.2 [E2E] Extend Playwright: the Listado view over a two-week range for one rep, and the refusal message for a range over 92 days.
- [x] 7.3 [E2E] Full compose smoke plus the complete Playwright suite (desktop + mobile, rate-limit swap, image rebuilt before the run so the suite tests the current bundle).
