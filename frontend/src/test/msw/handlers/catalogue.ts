import { http, HttpResponse } from 'msw';

import { doppler, products, type ProductRead } from '../catalogue-fixtures';
import { API_V1 } from '../constants';
import { problem } from '../fixtures';

function requireIfMatch(request: Request): Response | null {
  if (!request.headers.get('if-match')) {
    return problem(428, 'precondition_required', 'If-Match required');
  }
  return null;
}

/** Stateless defaults reflecting api-spec.yml; tests override with server.use(). */
export const catalogueHandlers = [
  http.get(`${API_V1}/products`, ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get('q')?.toLowerCase();
    const divisionId = url.searchParams.get('division_id');
    const brandId = url.searchParams.get('brand_id');
    const kind = url.searchParams.get('kind');
    const isActive = url.searchParams.get('is_active') ?? 'true';
    let items: ProductRead[] = products;
    if (q) {
      items = items.filter(
        (p) => p.sku.toLowerCase().startsWith(q) || p.name.toLowerCase().includes(q),
      );
    }
    if (divisionId) items = items.filter((p) => p.family.division_id === divisionId);
    if (brandId) items = items.filter((p) => p.brand.id === brandId);
    if (kind) items = items.filter((p) => p.kind === kind);
    if (isActive === 'true') items = items.filter((p) => p.is_active);
    if (isActive === 'false') items = items.filter((p) => !p.is_active);
    const page = Number(url.searchParams.get('page') ?? '1');
    const pageSize = Number(url.searchParams.get('page_size') ?? '25');
    return HttpResponse.json({
      items: items.slice((page - 1) * pageSize, page * pageSize),
      total: items.length,
      page,
      page_size: pageSize,
    });
  }),
  http.get(`${API_V1}/products/:id`, ({ params }) => {
    const product = products.find((p) => p.id === params.id);
    return product ? HttpResponse.json(product) : problem(404, 'not_found', 'Product not found');
  }),
  http.post(`${API_V1}/products`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...doppler,
        id: 'new-product-id',
        sku: String(body.sku).toUpperCase(),
        name: body.name,
        kind: body.kind,
        list_price: body.list_price,
        cost_price: body.cost_price ?? null,
        unit: body.unit ?? 'ud',
        description: body.description ?? null,
        version: 1,
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_V1}/products/:id`, async ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const body = (await request.json()) as Record<string, unknown>;
    const product = products.find((p) => p.id === params.id) ?? doppler;
    return HttpResponse.json({ ...product, ...body, version: product.version + 1 });
  }),
  http.post(`${API_V1}/products/:id/deactivate`, ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const product = products.find((p) => p.id === params.id) ?? doppler;
    return HttpResponse.json({ ...product, is_active: false, version: product.version + 1 });
  }),
  http.post(`${API_V1}/products/:id/activate`, ({ request, params }) => {
    const missing = requireIfMatch(request);
    if (missing) return missing;
    const product = products.find((p) => p.id === params.id) ?? doppler;
    return HttpResponse.json({ ...product, is_active: true, version: product.version + 1 });
  }),
];
