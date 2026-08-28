import { http, HttpResponse } from 'msw';

import { API_V1 } from '../constants';
import { problem } from '../fixtures';
import {
  board,
  doppler,
  opportunities,
  summaryOf,
  type OpportunityRead,
} from '../opportunities-fixtures';

function requireIfMatch(request: Request): Response | null {
  if (!request.headers.get('if-match')) {
    return problem(428, 'precondition_required', 'If-Match required');
  }
  return null;
}

function find(id: string | readonly string[] | undefined): OpportunityRead {
  return opportunities.find((o) => o.id === String(id ?? '')) ?? doppler;
}

/** Stateless defaults reflecting api-spec.yml; tests override with server.use(). */
export const opportunityHandlers = [
  http.get(`${API_V1}/opportunities`, ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get('status') ?? 'open';
    const q = url.searchParams.get('q')?.toLowerCase();
    let items = opportunities;
    if (status !== 'all') items = items.filter((o) => o.status === status);
    if (q) items = items.filter((o) => o.name.toLowerCase().includes(q));
    return HttpResponse.json({
      items: items.map(summaryOf),
      total: items.length,
      page: 1,
      page_size: 25,
    });
  }),
  http.get(`${API_V1}/opportunities/board`, () => HttpResponse.json(board)),
  http.get(`${API_V1}/opportunities/:id`, ({ params }) => {
    const opportunity = opportunities.find((o) => o.id === params.id);
    return opportunity
      ? HttpResponse.json(opportunity)
      : problem(404, 'not_found', 'Opportunity not found');
  }),
  http.get(`${API_V1}/accounts/:id/opportunities`, ({ params }) =>
    HttpResponse.json(opportunities.filter((o) => o.account_id === params.id).map(summaryOf)),
  ),
  http.post(`${API_V1}/opportunities`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...doppler,
        id: 'new-opportunity-id',
        account_id: body.account_id,
        division_id: body.division_id,
        estimated_amount: body.estimated_amount,
        amount: body.estimated_amount,
        is_tender: body.is_tender ?? false,
        stage_history: [],
        version: 1,
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_V1}/opportunities/:id`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const current = find(params.id);
    return HttpResponse.json({ ...current, ...body, version: current.version + 1 });
  }),
  http.post(`${API_V1}/opportunities/:id/stage`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { stage_id: string };
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      stage_id: body.stage_id,
      days_in_stage: 0,
      version: current.version + 1,
    });
  }),
  http.post(`${API_V1}/opportunities/:id/win`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { won_amount?: string };
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      status: 'won',
      stage_name: 'Ganada',
      won_amount: body.won_amount ?? current.amount,
      won_at: '2026-08-28T10:00:00Z',
      version: current.version + 1,
    });
  }),
  http.post(`${API_V1}/opportunities/:id/lose`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      status: 'lost',
      stage_name: 'Perdida',
      loss_reason_id: body.loss_reason_id,
      competitor_brand_id: body.competitor_brand_id ?? null,
      loss_note: body.note ?? null,
      lost_at: '2026-08-28T10:00:00Z',
      version: current.version + 1,
    });
  }),
  http.post(`${API_V1}/opportunities/:id/reopen`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { stage_id: string };
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      status: 'open',
      stage_id: body.stage_id,
      won_amount: null,
      won_at: null,
      version: current.version + 1,
    });
  }),
  http.post(`${API_V1}/opportunities/:id/at-risk`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { flag: boolean };
    const current = find(params.id);
    return HttpResponse.json({
      ...current,
      is_at_risk: body.flag,
      at_risk_since: body.flag ? '2026-08-28T10:00:00Z' : null,
      at_risk_source: body.flag ? 'manual' : null,
      version: current.version + 1,
    });
  }),
  http.put(`${API_V1}/opportunities/:id/assignment`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as { owner_id: string };
    const current = find(params.id);
    return HttpResponse.json({ ...current, owner_id: body.owner_id, version: current.version + 1 });
  }),
  http.post(`${API_V1}/opportunities/:id/lines`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as {
      product_id: string;
      quantity: string;
      unit_price?: string;
    };
    const current = find(params.id);
    const unitPrice = body.unit_price ?? '12500.00';
    const total = (Number(body.quantity) * Number(unitPrice)).toFixed(2);
    return HttpResponse.json(
      {
        ...current,
        amount: total,
        lines: [
          {
            id: 'line-1',
            product_id: body.product_id,
            quantity: Number(body.quantity).toFixed(2),
            unit_price: unitPrice,
            total,
            sort_order: 10,
          },
        ],
        version: current.version + 1,
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_V1}/opportunities/:id/lines/:lineId`, ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const current = find(params.id);
    return HttpResponse.json({ ...current, version: current.version + 1 });
  }),
  http.delete(`${API_V1}/opportunities/:id/lines/:lineId`, ({ request }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    return new HttpResponse(null, { status: 204 });
  }),
];
