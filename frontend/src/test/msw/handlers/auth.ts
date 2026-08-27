import { http, HttpResponse } from 'msw';

import { API_V1 } from '../constants';
import { adminUser, problem } from '../fixtures';

export const authHandlers = [
  http.post(`${API_V1}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.email === adminUser.email && body.password === 'correct-horse-battery') {
      return HttpResponse.json({
        access_token: 'access-token-admin',
        token_type: 'bearer',
        expires_in: 900,
        user: adminUser,
      });
    }
    return problem(401, 'invalid_credentials', 'Email or password is incorrect');
  }),
  http.post(`${API_V1}/auth/refresh`, () =>
    HttpResponse.json({
      access_token: 'access-token-refreshed',
      token_type: 'bearer',
      expires_in: 900,
      user: adminUser,
    }),
  ),
  http.post(`${API_V1}/auth/logout`, () => new HttpResponse(null, { status: 204 })),
  http.get(`${API_V1}/me`, ({ request }) => {
    if (!request.headers.get('authorization')) {
      return problem(401, 'unauthenticated', 'Missing bearer token');
    }
    return HttpResponse.json({ ...adminUser, territories: [], divisions: [] });
  }),
];
