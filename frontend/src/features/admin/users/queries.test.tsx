import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { Providers, createQueryClient } from '@/app/providers';
import { REP_ID, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';

import { useCreateUser, useUpdateUser, useUser, useUsers } from './queries';

function wrapper({ children }: { children: ReactNode }) {
  return <Providers queryClient={createQueryClient()}>{children}</Providers>;
}

describe('user queries', () => {
  it('sends filters as query params', async () => {
    let search = '';
    server.use(
      http.get(`${API_V1}/users`, ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json({ items: [repUser], total: 1, page: 1, page_size: 50 });
      }),
    );

    const { result } = renderHook(
      () => useUsers({ q: 'an', role: 'sales_rep', is_active: 'true' }),
      {
        wrapper,
      },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(search).toBe('?q=an&role=sales_rep&is_active=true');
    expect(result.current.data?.items[0]?.id).toBe(REP_ID);
  });

  it('loads a single user and skips the request without an id', async () => {
    const { result } = renderHook(() => useUser(REP_ID), { wrapper });
    await waitFor(() => {
      expect(result.current.data?.full_name).toBe('Ana García');
    });

    const { result: disabled } = renderHook(() => useUser(undefined), { wrapper });
    expect(disabled.current.fetchStatus).toBe('idle');
  });

  it('creates a user with the given payload', async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/users`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...repUser, id: 'created' }, { status: 201 });
      }),
    );
    const { result } = renderHook(() => useCreateUser(), { wrapper });

    const created = await result.current.mutateAsync({
      email: 'nueva@quermed.com',
      full_name: 'Nueva',
      role: 'sales_rep',
      password: 'correct-horse-battery',
      territory_ids: [],
      division_ids: [],
    });

    expect(created.id).toBe('created');
    expect(body.email).toBe('nueva@quermed.com');
  });

  it('updates a user sending the If-Match version', async () => {
    let ifMatch: string | null = null;
    server.use(
      http.patch(`${API_V1}/users/:id`, ({ request }) => {
        ifMatch = request.headers.get('if-match');
        return HttpResponse.json({ ...repUser, full_name: 'Renamed', version: 4 });
      }),
    );
    const { result } = renderHook(() => useUpdateUser(), { wrapper });

    const updated = await result.current.mutateAsync({
      id: REP_ID,
      version: 3,
      payload: { full_name: 'Renamed' },
    });

    expect(ifMatch).toBe('"3"');
    expect(updated.version).toBe(4);
  });
});
