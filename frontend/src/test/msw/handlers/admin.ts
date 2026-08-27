import { http, HttpResponse } from 'msw';

import { API_V1 } from '../constants';
import {
  adminUser,
  page,
  problem,
  repUser,
  territories,
  type TerritoryRead,
  type UserRead,
} from '../fixtures';

/** Stateless defaults reflecting api-spec.yml; tests override with server.use() for specifics. */
export const adminHandlers = [
  http.get(`${API_V1}/users`, ({ request }) => {
    const url = new URL(request.url);
    let items: UserRead[] = [adminUser, repUser];
    const role = url.searchParams.get('role');
    const isActive = url.searchParams.get('is_active');
    const q = url.searchParams.get('q')?.toLowerCase();
    if (role) items = items.filter((user) => user.role === role);
    if (isActive) items = items.filter((user) => String(user.is_active) === isActive);
    if (q) {
      items = items.filter(
        (user) => user.full_name.toLowerCase().startsWith(q) || user.email.startsWith(q),
      );
    }
    return HttpResponse.json(page(items));
  }),
  http.get(`${API_V1}/users/:id`, ({ params }) => {
    const user = [adminUser, repUser].find((candidate) => candidate.id === params.id);
    return user ? HttpResponse.json(user) : problem(404, 'not_found', 'User not found');
  }),
  http.post(`${API_V1}/users`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        ...repUser,
        id: 'new-user-id',
        email: String(body.email).toLowerCase(),
        full_name: body.full_name,
        role: body.role,
        territory_ids: body.territory_ids,
        division_ids: body.division_ids,
      },
      { status: 201 },
    );
  }),
  http.patch(`${API_V1}/users/:id`, async ({ request, params }) => {
    if (!request.headers.get('if-match')) {
      return problem(428, 'precondition_required', 'If-Match required');
    }
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ ...repUser, id: params.id, ...body, version: 2 });
  }),
  http.get(`${API_V1}/territories/:id`, ({ params }) => {
    const territory = territories.find((candidate) => candidate.id === params.id);
    return territory
      ? HttpResponse.json(territory)
      : problem(404, 'not_found', 'Territory not found');
  }),
  http.post(`${API_V1}/territories`, async ({ request }) => {
    const body = (await request.json()) as { name: string; provinces: string[] };
    const created: TerritoryRead = {
      ...territories[0]!,
      id: 'new-territory-id',
      name: body.name,
      provinces: [...body.provinces].sort(),
      user_count: 0,
    };
    return HttpResponse.json(created, { status: 201 });
  }),
  http.patch(`${API_V1}/territories/:id`, async ({ request, params }) => {
    if (!request.headers.get('if-match')) {
      return problem(428, 'precondition_required', 'If-Match required');
    }
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ ...territories[0]!, id: params.id, ...body, version: 2 });
  }),
];
