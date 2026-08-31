import { http, HttpResponse } from 'msw';

import {
  accounts,
  ana,
  bea,
  contactSummaries,
  contacts,
  summaryOf,
  tambre,
  type AccountRead,
} from '../accounts-fixtures';
import { API_V1 } from '../constants';
import { problem } from '../fixtures';

function requireIfMatch(request: Request): Response | null {
  if (!request.headers.get('if-match')) {
    return problem(428, 'precondition_required', 'If-Match required');
  }
  return null;
}

/** Stateless defaults reflecting api-spec.yml; tests override with server.use(). */
export const accountHandlers = [
  http.get(`${API_V1}/accounts`, ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get('q')?.toLowerCase();
    const typeId = url.searchParams.get('account_type_id');
    const unassigned = url.searchParams.get('unassigned') === 'true';
    const isActive = url.searchParams.get('is_active');
    let items: AccountRead[] = accounts;
    if (q) items = items.filter((a) => a.name.toLowerCase().includes(q));
    if (typeId) items = items.filter((a) => a.account_type_id === typeId);
    if (unassigned) items = items.filter((a) => a.owner_id === null);
    if (isActive === 'false') items = items.filter((a) => !a.is_active);
    const page = Number(url.searchParams.get('page') ?? '1');
    const pageSize = Number(url.searchParams.get('page_size') ?? '50');
    const slice = items.slice((page - 1) * pageSize, page * pageSize);
    return HttpResponse.json({
      items: slice.map((a) => summaryOf(a, a.id === tambre.id ? 'Ana Pérez' : null)),
      total: items.length,
      page,
      page_size: pageSize,
    });
  }),
  http.post(`${API_V1}/accounts`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...tambre,
        id: 'new-account-id',
        name: body.name,
        account_type_id: body.account_type_id,
        province_code: body.province_code,
        tax_id: body.tax_id ?? null,
        city: body.city ?? null,
        division_ids: body.division_ids ?? [],
        brand_ids: body.brand_ids ?? [],
        addresses: [],
        version: 1,
      },
      { status: 201 },
    );
  }),
  http.get(`${API_V1}/accounts/:id`, ({ params }) => {
    const account = accounts.find((a) => a.id === params.id);
    return account ? HttpResponse.json(account) : problem(404, 'not_found', 'Account not found');
  }),
  http.patch(`${API_V1}/accounts/:id`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const account = accounts.find((a) => a.id === params.id) ?? tambre;
    return HttpResponse.json({ ...account, ...body, version: account.version + 1 });
  }),
  http.put(`${API_V1}/accounts/:id/assignment`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const account = accounts.find((a) => a.id === params.id) ?? tambre;
    return HttpResponse.json({
      ...account,
      ...(body.owner_id !== undefined
        ? { owner_id: body.owner_id, owner_name: 'Nuevo Comercial' }
        : {}),
      ...(body.territory_id !== undefined ? { territory_id: body.territory_id } : {}),
      version: account.version + 1,
    });
  }),
  http.put(`${API_V1}/accounts/:id/addresses`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { addresses: AccountRead['addresses'] };
    const account = accounts.find((a) => a.id === params.id) ?? tambre;
    return HttpResponse.json({
      ...account,
      addresses: body.addresses.map((a) => ({ ...a, notes: a.notes ?? null })),
      version: account.version + 1,
    });
  }),
  /** The global contacts list: cumulative filters, exactly like the API. */
  http.get(`${API_V1}/contacts`, ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get('q')?.toLowerCase();
    const specialtyIds = url.searchParams.getAll('specialty_id');
    const accountIds = url.searchParams.getAll('account_id');
    const heads = url.searchParams.get('is_head_of_department') === 'true';
    let items = contactSummaries;
    if (q) {
      items = items.filter((c) => `${c.first_name} ${c.last_name}`.toLowerCase().includes(q));
    }
    if (specialtyIds.length > 0) {
      items = items.filter((c) => c.specialty_id !== null && specialtyIds.includes(c.specialty_id));
    }
    if (accountIds.length > 0) items = items.filter((c) => accountIds.includes(c.account_id));
    if (heads) items = items.filter((c) => c.is_head_of_department);
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 50 });
  }),

  http.get(`${API_V1}/accounts/:id/contacts`, ({ params }) =>
    params.id === tambre.id
      ? HttpResponse.json(contacts)
      : accounts.some((a) => a.id === params.id)
        ? HttpResponse.json([])
        : problem(404, 'not_found', 'Account not found'),
  ),
  http.post(`${API_V1}/accounts/:id/contacts`, async ({ request, params }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...bea,
        id: 'new-contact-id',
        account_id: params.id,
        first_name: body.first_name,
        last_name: body.last_name,
        is_primary: body.is_primary ?? false,
        version: 1,
      },
      { status: 201 },
    );
  }),
  http.get(`${API_V1}/contacts/:id`, ({ params }) => {
    const contact = contacts.find((c) => c.id === params.id);
    return contact ? HttpResponse.json(contact) : problem(404, 'not_found', 'Contact not found');
  }),
  http.patch(`${API_V1}/contacts/:id`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const contact = contacts.find((c) => c.id === params.id) ?? ana;
    const { consent, ...rest } = body;
    return HttpResponse.json({
      ...contact,
      ...rest,
      ...(consent ? { consent: { recorded_by: null, at: null, source: null, ...consent } } : {}),
      version: contact.version + 1,
    });
  }),
  http.post(`${API_V1}/contacts/:id/anonymise`, ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const contact = contacts.find((c) => c.id === params.id) ?? ana;
    return HttpResponse.json({
      ...contact,
      first_name: 'Contacto',
      last_name: 'anonimizado',
      email: null,
      mobile: null,
      landline: null,
      notes: null,
      preferred_channel: null,
      is_primary: false,
      is_active: false,
      anonymised_at: '2026-08-28T12:00:00Z',
      consent: { status: 'denied', at: '2026-08-28T12:00:00Z', source: 'form', recorded_by: null },
      version: contact.version + 1,
    });
  }),
];
