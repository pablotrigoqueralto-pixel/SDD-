import { http, HttpResponse } from 'msw';

import { API_V1 } from '../constants';
import { divisions, page, problem, territories } from '../fixtures';
import { brands, lossReasons, pipelines, referenceBundle } from '../reference-fixtures';

/** Stateless defaults; tests override with server.use() for specific scenarios. */
export const referenceHandlers = [
  http.get(`${API_V1}/divisions`, () => HttpResponse.json(divisions)),
  http.get(`${API_V1}/territories`, () => HttpResponse.json(page(territories))),
  http.get(`${API_V1}/reference-data`, () =>
    HttpResponse.json(referenceBundle, { headers: { ETag: '"test-etag"' } }),
  ),
  http.get(`${API_V1}/brands`, ({ request }) => {
    const url = new URL(request.url);
    const isOwn = url.searchParams.get('is_own');
    const q = url.searchParams.get('q')?.toLowerCase();
    let items = brands;
    if (isOwn) items = items.filter((b) => String(b.is_own) === isOwn);
    if (q) items = items.filter((b) => b.name.toLowerCase().startsWith(q));
    return HttpResponse.json(items);
  }),
  http.post(`${API_V1}/brands`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...brands[0]!,
        id: 'new-brand-id',
        code: 'new_brand',
        name: body.name,
        is_own: body.is_own,
        division_ids: body.division_ids ?? [],
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_V1}/brands/:id`, async ({ request, params }) => {
    if (!request.headers.get('if-match')) {
      return problem(428, 'precondition_required', 'If-Match required');
    }
    const body = (await request.json()) as Record<string, unknown>;
    const current = brands.find((b) => b.id === params.id) ?? brands[0]!;
    return HttpResponse.json({ ...current, ...body, version: current.version + 1 });
  }),
  http.get(`${API_V1}/loss-reasons`, () => HttpResponse.json(lossReasons)),
  http.post(`${API_V1}/loss-reasons`, async ({ request }) => {
    const body = (await request.json()) as { name: string };
    return HttpResponse.json(
      {
        ...lossReasons[0]!,
        id: 'new-reason-id',
        code: 'new_reason',
        name_es: body.name,
        sort_order: 70,
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_V1}/loss-reasons/:id`, async ({ request, params }) => {
    if (!request.headers.get('if-match')) {
      return problem(428, 'precondition_required', 'If-Match required');
    }
    const body = (await request.json()) as Record<string, unknown>;
    const current = lossReasons.find((r) => r.id === params.id) ?? lossReasons[0]!;
    return HttpResponse.json({
      ...current,
      ...(typeof body.name === 'string' ? { name_es: body.name } : {}),
      ...(typeof body.is_active === 'boolean' ? { is_active: body.is_active } : {}),
      version: current.version + 1,
    });
  }),
  http.get(`${API_V1}/pipelines`, () => HttpResponse.json(pipelines)),
  http.patch(`${API_V1}/pipelines/:id/stages/:stageId`, async ({ request, params }) => {
    if (!request.headers.get('if-match')) {
      return problem(428, 'precondition_required', 'If-Match required');
    }
    const body = (await request.json()) as Record<string, unknown>;
    const pipeline = pipelines.find((p) => p.id === params.id) ?? pipelines[0]!;
    return HttpResponse.json({
      ...pipeline,
      stages: pipeline.stages.map((s) =>
        s.id === params.stageId
          ? {
              ...s,
              ...(typeof body.name === 'string' ? { name_es: body.name } : {}),
              ...(typeof body.probability === 'number' ? { probability: body.probability } : {}),
              ...(typeof body.is_active === 'boolean' ? { is_active: body.is_active } : {}),
              version: s.version + 1,
            }
          : s,
      ),
    });
  }),
  http.put(`${API_V1}/pipelines/:id/stages/order`, async ({ request, params }) => {
    if (!request.headers.get('if-match')) {
      return problem(428, 'precondition_required', 'If-Match required');
    }
    const body = (await request.json()) as { stage_ids: string[] };
    const pipeline = pipelines.find((p) => p.id === params.id) ?? pipelines[0]!;
    const byId = new Map(pipeline.stages.map((s) => [s.id, s]));
    return HttpResponse.json({
      ...pipeline,
      version: pipeline.version + 1,
      stages: body.stage_ids.map((id, index) => ({ ...byId.get(id)!, sort_order: index + 1 })),
    });
  }),
];
