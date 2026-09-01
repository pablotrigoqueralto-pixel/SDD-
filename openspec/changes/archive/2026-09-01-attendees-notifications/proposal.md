## Why

Last three items of the sales director's feedback, and they turn out to be one story. A visit is often made by two people from Quermed, but an activity has exactly one owner and no way to say "Andrés comes with me" — the second rep's day simply does not show it. Worse, **when a manager plans something for someone else, nobody tells them**: the activity lands in their agenda silently and they find it, or they do not. And when the boss asks "¿qué hizo el equipo entre el 1 y el 15?", the agenda only offers a day and a month view: there is no way to list a date range for one person.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **An activity can carry several Quermed colleagues as attendees** (`activity_attendees`), alongside the centre's contacts it already records. An attendee sees the activity in their own "Hoy" and month calendar, **marked as invited** so it never looks like their own work; the owner stays the only one who completes, reschedules or cancels it.
- **A notifications block on "Hoy" and a bell with a counter in the header**: the CRM tells you what somebody else has put on your plate — you were added as an attendee, an activity was created with you as owner, a centre was assigned to you, an opportunity was reassigned to you. The rule is "another person assigned this to you": your own actions never notify you, or your own work would bury the block.
- **Notifications are read and gone**: opening one takes you to what it is about and marks it read; "Marcar todo como leído" clears the block. Read ones leave the block rather than piling into a history nobody revisits.
- **A third "Listado" view in the agenda**, beside Día and Mes: from/to dates and a rep selector, activities listed by date with their centre, type and state. Staff may list any rep; a rep lists their own.
- No email: the notice lives inside the CRM, where the day starts.

## Capabilities

### New Capabilities
- `notification-model`: the notifications table — what is stored for a notice, who owns it, its read state, which events create one and the rule that an actor never notifies themselves.
- `notification-api`: `GET /api/v1/notifications` (unread by default, with the count), marking one or all as read, and the events the writing services emit.

### Modified Capabilities
- `activity-model`: activities gain `activity_attendees` (internal users), with the invariants that keep an attendee from replacing the owner.
- `activity-api`: attendees travel in the activity payloads; "Hoy" and the calendar include the activities a user attends, flagged as invited; the calendar feed accepts a date range.
- `activity-screens`: the attendees field in the activity form, the invited badge on Hoy and the month calendar, and the new "Listado" view with its range and rep filters.
- `app-shell`: the header gains the notifications bell with its unread counter.
- `account-contact-api`: assigning a centre to somebody else notifies them.
- `opportunity-api`: reassigning an opportunity to somebody else notifies them.

## Non-goals

- No email or push: in-app only, as agreed.
- No free-text attendees: only Quermed users. The centre's people are already recorded as contacts, and a typed name could not be filtered or reused.
- No attendee completing, rescheduling or cancelling: one owner per activity, unchanged.
- No notification preferences screen: the four events are the whole set, and none of them is noise a user would want to switch off.
- No notification history: read means gone from the block. The audit log already records who did what, and forever.
- No export from the "Listado" view: a report to download is a different feature nobody has asked for yet.
- No changes to the day or month views beyond the invited badge.

## Impact

- **Roles**: unchanged. An attendee sees an activity because it belongs to an account they can already see (a rep is only added to activities of centres in their scope); notifications are strictly per-user and readable by nobody else.
- **Backend**: `activity_attendees` and `notifications` tables with migration `0011`, attendees in the activity service and payloads, the today/calendar queries widened to "owned or attended", a range on the calendar feed, the notification writes emitted by the activity, account and opportunity services, and `api-spec.yml` regenerated.
- **Frontend**: a `notifications` feature (bell, block on Hoy, mark-as-read mutations, polling on focus), the attendees field in the activity form, the invited badge on the Hoy cards and calendar, the third agenda view with its filters, and the `activities`/`common` i18n growth.
- **Docs**: `data-model.md` (both tables, the notification events, the attendee invariants), `development_guide.md` (what notifies and what does not, the invited rule, the Listado view), `api-spec.yml`.
- **Constitution principles served**: 30-second interactions (what is new for you is on the first screen, not hunted for), data honesty (an invited activity is labelled as invited, not disguised as your own), and one screen one purpose (the agenda gains a third view instead of overloading the month grid with filters).
