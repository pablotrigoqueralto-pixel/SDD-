import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/store/session.store';
import { adminUser, problem } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';

import { apiClient, ifMatch } from './client';

describe('apiClient', () => {
  beforeEach(() => {
    sessionStore.getState().clear();
  });

  it('attaches the bearer token from the session store', async () => {
    sessionStore.getState().setSession('token-123', adminUser);
    let seen: string | null = null;
    server.use(
      http.get(`${API_V1}/probe`, ({ request }) => {
        seen = request.headers.get('authorization');
        return HttpResponse.json({ ok: true });
      }),
    );

    await apiClient.get('/probe');

    expect(seen).toBe('Bearer token-123');
  });

  it('refreshes once on 401 and retries the request with the new token', async () => {
    sessionStore.getState().setSession('stale', adminUser);
    const authorizations: string[] = [];
    let refreshCalls = 0;
    server.use(
      http.get(`${API_V1}/probe`, ({ request }) => {
        const auth = request.headers.get('authorization') ?? '';
        authorizations.push(auth);
        if (auth === 'Bearer stale') {
          return problem(401, 'unauthenticated', 'expired');
        }
        return HttpResponse.json({ ok: true });
      }),
      http.post(`${API_V1}/auth/refresh`, () => {
        refreshCalls += 1;
        return HttpResponse.json({
          access_token: 'fresh',
          token_type: 'bearer',
          expires_in: 900,
          user: adminUser,
        });
      }),
    );

    const [first, second] = await Promise.all([apiClient.get('/probe'), apiClient.get('/probe')]);

    expect(first.status).toBe(200);
    expect(second.status).toBe(200);
    expect(refreshCalls).toBe(1);
    expect(authorizations).toEqual([
      'Bearer stale',
      'Bearer stale',
      'Bearer fresh',
      'Bearer fresh',
    ]);
    expect(sessionStore.getState().accessToken).toBe('fresh');
  });

  it('clears the session when the refresh fails', async () => {
    sessionStore.getState().setSession('stale', adminUser);
    server.use(
      http.get(`${API_V1}/probe`, () => problem(401, 'unauthenticated', 'expired')),
      http.post(`${API_V1}/auth/refresh`, () => problem(401, 'unauthenticated', 'no cookie')),
    );

    await expect(apiClient.get('/probe')).rejects.toMatchObject({ code: 'unauthenticated' });

    expect(sessionStore.getState().status).toBe('anonymous');
    expect(sessionStore.getState().accessToken).toBeNull();
  });

  it('does not try to refresh on a failed login', async () => {
    let refreshCalls = 0;
    server.use(
      http.post(`${API_V1}/auth/refresh`, () => {
        refreshCalls += 1;
        return HttpResponse.json({});
      }),
    );

    await expect(
      apiClient.post('/auth/login', { email: 'x@quermed.com', password: 'bad' }),
    ).rejects.toMatchObject({ code: 'invalid_credentials', status: 401 });

    expect(refreshCalls).toBe(0);
  });

  it('normalises problem+json errors', async () => {
    server.use(
      http.get(`${API_V1}/probe`, () =>
        problem(422, 'validation_error', 'Invalid', [
          { field: 'email', message: 'Invalid email', code: 'invalid_email' },
        ]),
      ),
    );

    await expect(apiClient.get('/probe')).rejects.toMatchObject({
      status: 422,
      code: 'validation_error',
      errors: [{ field: 'email', code: 'invalid_email', message: 'Invalid email' }],
    });
  });

  it('builds the If-Match header with a quoted version', () => {
    expect(ifMatch(3)).toEqual({ 'If-Match': '"3"' });
  });
});
