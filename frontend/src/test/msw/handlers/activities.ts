import { http, HttpResponse } from 'msw';

import { accounts } from '../accounts-fixtures';
import { activities, timeline, today, visitDone, type ActivityRead } from '../activities-fixtures';
import { API_V1 } from '../constants';
import { problem } from '../fixtures';

function requireIfMatch(request: Request): Response | null {
  if (!request.headers.get('if-match')) {
    return problem(428, 'precondition_required', 'If-Match required');
  }
  return null;
}

function find(id: string | readonly string[] | undefined): ActivityRead {
  return activities.find((a) => a.id === id) ?? visitDone;
}

export const CAL_REP_LAURA = '019000000-0000-7000-8000-00000000ca01';
export const CAL_REP_PEDRO = '019000000-0000-7000-8000-00000000ca02';

/** Deterministic month payload: entries pinned to days 10 and 14 of the requested month. */
export function calendarPayload(year: number, month: number) {
  const day = (d: number) =>
    `${String(year)}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  return {
    year,
    month,
    total: 3,
    items: [
      {
        id: '019000000-0000-7000-8000-00000000ce01',
        occurred_on: day(10),
        occurred_time: '10:00',
        status: 'planned',
        activity_type: { code: 'visit', name: 'Visita', icon: 'map-pin' },
        account_id: accounts[0]!.id,
        account_name: accounts[0]!.name,
        owner_id: CAL_REP_LAURA,
        owner_name: 'Laura Vendedora',
      },
      {
        id: '019000000-0000-7000-8000-00000000ce02',
        occurred_on: day(14),
        occurred_time: '09:30',
        status: 'done',
        activity_type: { code: 'call', name: 'Llamada', icon: 'phone' },
        account_id: accounts[0]!.id,
        account_name: accounts[0]!.name,
        owner_id: CAL_REP_LAURA,
        owner_name: 'Laura Vendedora',
      },
      {
        id: '019000000-0000-7000-8000-00000000ce03',
        occurred_on: day(14),
        occurred_time: '16:00',
        status: 'planned',
        activity_type: { code: 'visit', name: 'Visita', icon: 'map-pin' },
        account_id: accounts[0]!.id,
        account_name: accounts[0]!.name,
        owner_id: CAL_REP_PEDRO,
        owner_name: 'Pedro Vendedor',
      },
    ],
  };
}

/** Stateless defaults reflecting api-spec.yml; tests override with server.use(). */
export const activityHandlers = [
  // Every authenticated screen renders the bell, so the inbox must always answer.
  http.get(`${API_V1}/notifications`, () => HttpResponse.json({ items: [], unread_count: 0 })),
  http.post(`${API_V1}/notifications/read-all`, () =>
    HttpResponse.json({ items: [], unread_count: 0 }),
  ),
  http.post(`${API_V1}/notifications/:id/read`, () =>
    HttpResponse.json({ items: [], unread_count: 0 }),
  ),
  http.get(`${API_V1}/activities/calendar`, ({ request }) => {
    const url = new URL(request.url);
    const year = Number(url.searchParams.get('year'));
    const month = Number(url.searchParams.get('month'));
    const ownerId = url.searchParams.get('owner_id');
    const payload = calendarPayload(year, month);
    if (ownerId) {
      const items = payload.items.filter((item) => item.owner_id === ownerId);
      return HttpResponse.json({ ...payload, total: items.length, items });
    }
    return HttpResponse.json(payload);
  }),
  http.get(`${API_V1}/activities`, ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get('status');
    const items = status ? activities.filter((a) => a.status === status) : activities;
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 25 });
  }),
  http.post(`${API_V1}/activities`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const account = accounts.find((a) => a.id === body.account_id);
    return HttpResponse.json(
      {
        ...visitDone,
        id: 'new-activity-id',
        account_id: body.account_id,
        account_name: account?.name ?? 'Centro',
        activity_type_id: body.activity_type_id,
        status: body.status ?? 'done',
        scheduled_at: body.scheduled_at ?? new Date().toISOString(),
        done_at: (body.status ?? 'done') === 'done' ? new Date().toISOString() : null,
        subject: body.subject ?? null,
        notes: body.notes ?? null,
        outcome: body.outcome ?? null,
        contact_ids: body.contact_ids ?? [],
        contacts: [],
        next_activity_id: body.next_action ? 'follow-up-id' : null,
        version: 1,
      },
      { status: 201 },
    );
  }),
  http.get(`${API_V1}/activities/:id`, ({ params }) => {
    const activity = activities.find((a) => a.id === params.id);
    return activity ? HttpResponse.json(activity) : problem(404, 'not_found', 'Activity not found');
  }),
  http.patch(`${API_V1}/activities/:id`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const activity = find(params.id);
    return HttpResponse.json({ ...activity, ...body, version: activity.version + 1 });
  }),
  http.post(`${API_V1}/activities/:id/complete`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const activity = find(params.id);
    return HttpResponse.json({
      ...activity,
      status: 'done',
      done_at: new Date().toISOString(),
      outcome: body.outcome ?? null,
      notes: body.notes ?? activity.notes,
      next_activity_id: body.next_action ? 'follow-up-id' : null,
      version: activity.version + 1,
    });
  }),
  http.post(`${API_V1}/activities/:id/cancel`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { reason: string };
    const activity = find(params.id);
    return HttpResponse.json({
      ...activity,
      status: 'cancelled',
      cancel_reason: body.reason,
      version: activity.version + 1,
    });
  }),
  http.post(`${API_V1}/activities/:id/reschedule`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { scheduled_at: string };
    const activity = find(params.id);
    return HttpResponse.json({
      ...activity,
      scheduled_at: body.scheduled_at,
      version: activity.version + 1,
    });
  }),
  http.get(`${API_V1}/accounts/:id/timeline`, ({ request, params }) => {
    if (!accounts.some((a) => a.id === params.id)) {
      return problem(404, 'not_found', 'Account not found');
    }
    const url = new URL(request.url);
    const pageSize = Number(url.searchParams.get('page_size') ?? '25');
    const status = url.searchParams.get('status');
    const items = status ? timeline.filter((e) => e.activity!.status === status) : timeline;
    return HttpResponse.json({
      items: items.slice(0, pageSize),
      total: items.length,
      page: 1,
      page_size: pageSize,
    });
  }),
  http.get(`${API_V1}/me/today`, () => HttpResponse.json(today)),
];
