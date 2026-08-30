import { http, HttpResponse } from 'msw';

import { API_V1 } from '../constants';
import { problem } from '../fixtures';
import {
  draftQuote,
  quoteSettings,
  quotes,
  summaryOfQuote,
  type QuoteRead,
} from '../quotes-fixtures';

function requireIfMatch(request: Request): Response | null {
  if (!request.headers.get('if-match')) {
    return problem(428, 'precondition_required', 'If-Match required');
  }
  return null;
}

function find(id: string | readonly string[] | undefined): QuoteRead {
  return quotes.find((quote) => quote.id === String(id ?? '')) ?? draftQuote;
}

/** Stateless defaults reflecting api-spec.yml; tests override with server.use(). */
export const quoteHandlers = [
  http.get(`${API_V1}/quotes`, ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get('status');
    const expiring = url.searchParams.get('expiring') === 'true';
    const q = url.searchParams.get('q')?.toLowerCase();
    let items = quotes;
    if (status && status !== 'all') items = items.filter((quote) => quote.status === status);
    if (expiring) items = items.filter((quote) => quote.status === 'sent');
    if (q) {
      items = items.filter(
        (quote) =>
          quote.display_number.toLowerCase().includes(q) ||
          quote.account_name.toLowerCase().includes(q),
      );
    }
    return HttpResponse.json({
      items: items.map(summaryOfQuote),
      total: items.length,
      page: 1,
      page_size: 25,
    });
  }),
  http.get(`${API_V1}/opportunities/:id/quotes`, ({ params }) =>
    HttpResponse.json(
      quotes.filter((quote) => quote.opportunity_id === params.id).map(summaryOfQuote),
    ),
  ),
  http.get(`${API_V1}/quotes/:id/pdf`, () =>
    HttpResponse.arrayBuffer(new TextEncoder().encode('%PDF-1.7 fake').buffer, {
      headers: { 'Content-Type': 'application/pdf' },
    }),
  ),
  http.get(`${API_V1}/quotes/:id`, ({ params }) => {
    const quote = quotes.find((entry) => entry.id === params.id);
    return quote ? HttpResponse.json(quote) : problem(404, 'not_found', 'Quote not found');
  }),
  http.post(`${API_V1}/quotes`, async ({ request }) => {
    const body = (await request.json()) as { opportunity_id: string; contact_id?: string };
    return HttpResponse.json(
      {
        ...draftQuote,
        id: 'new-quote-id',
        opportunity_id: body.opportunity_id,
        contact_id: body.contact_id ?? null,
        quote_number: 'P-2026-0009',
        display_number: 'P-2026-0009',
        version: 1,
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_V1}/quotes/:id`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      ...(body.conditions ? { conditions: body.conditions } : {}),
      version: current.version + 1,
    });
  }),
  http.delete(`${API_V1}/quotes/:id`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${API_V1}/quotes/:id/send`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { skip_email?: boolean; valid_until?: string };
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      status: 'sent',
      sent_at: '2026-08-28T10:00:00Z',
      valid_until: body.valid_until ?? '2026-09-27',
      email_status: body.skip_email ? 'skipped' : 'sent',
      version: current.version + 1,
    });
  }),
  http.post(`${API_V1}/quotes/:id/accept`, ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      status: 'accepted',
      accepted_at: '2026-08-28T10:00:00Z',
      version: current.version + 1,
    });
  }),
  http.post(`${API_V1}/quotes/:id/reject`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { note?: string };
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      status: 'rejected',
      rejected_at: '2026-08-28T10:00:00Z',
      rejection_note: body.note ?? null,
      version: current.version + 1,
    });
  }),
  http.post(`${API_V1}/quotes/:id/revise`, ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const current = find(params.id);
    return HttpResponse.json(
      {
        ...current,
        id: `${current.id}-v2`,
        status: 'draft',
        revision: current.revision + 1,
        display_number: `${current.quote_number}-v${current.revision + 1}`,
        sent_at: null,
        valid_until: null,
        version: 1,
      },
      { status: 201 },
    );
  }),
  http.post(`${API_V1}/quotes/:id/retry-email`, ({ params }) => {
    const current = find(params.id);
    return HttpResponse.json({ ...current, email_status: 'sent', email_error: null });
  }),
  http.get(`${API_V1}/quote-settings`, () => HttpResponse.json(quoteSettings)),
  http.put(`${API_V1}/quote-settings`, async ({ request }) =>
    HttpResponse.json(await request.json()),
  ),
];
