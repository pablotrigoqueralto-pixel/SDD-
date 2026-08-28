import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { useJobTitles } from '@/features/reference';
import { accounts, summaryOf, tambre } from '@/test/msw/accounts-fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { createTestQueryClient } from '@/test/render';

import {
  useAccount,
  useAccounts,
  useAssignAccount,
  useCreateAccount,
  useInfiniteAccounts,
  useReplaceAddresses,
  useUpdateAccount,
} from './queries';

function wrapperFor(queryClient = createTestQueryClient()) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { Wrapper, queryClient };
}

describe('account queries', () => {
  it('lists with filters mapped to query params (empty values dropped)', async () => {
    let url: URL | null = null;
    server.use(
      http.get(`${API_V1}/accounts`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({
          items: [summaryOf(tambre, null)],
          total: 1,
          page: 1,
          page_size: 25,
        });
      }),
    );
    const { Wrapper } = wrapperFor();

    const { result } = renderHook(
      () => useAccounts({ q: 'tam', account_type_id: '', unassigned: true, sort: '-city' }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    const params = url!.searchParams;
    expect(params.get('q')).toBe('tam');
    expect(params.get('account_type_id')).toBeNull();
    expect(params.get('unassigned')).toBe('true');
    expect(params.get('sort')).toBe('-city');
    expect(params.get('page_size')).toBe('25');
  });

  it('loads following pages with the infinite list until the total is reached', async () => {
    const many = Array.from({ length: 30 }, (_, index) => ({
      ...summaryOf(tambre, null),
      id: `acc-${index}`,
      name: `Centro ${index}`,
    }));
    server.use(
      http.get(`${API_V1}/accounts`, ({ request }) => {
        const url = new URL(request.url);
        const page = Number(url.searchParams.get('page') ?? '1');
        return HttpResponse.json({
          items: many.slice((page - 1) * 25, page * 25),
          total: many.length,
          page,
          page_size: 25,
        });
      }),
    );
    const { Wrapper } = wrapperFor();

    const { result } = renderHook(() => useInfiniteAccounts({}), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.hasNextPage).toBe(true);
    await result.current.fetchNextPage();
    await waitFor(() => {
      expect(result.current.data?.pages).toHaveLength(2);
    });
    expect(result.current.hasNextPage).toBe(false);
  });

  it('reads the detail and the job titles from the reference bundle', async () => {
    const { Wrapper } = wrapperFor();

    const detail = renderHook(() => useAccount(tambre.id), { wrapper: Wrapper });
    const titles = renderHook(() => useJobTitles(), { wrapper: Wrapper });

    await waitFor(() => {
      expect(detail.result.current.data?.name).toBe('Clínica Tambre');
    });
    await waitFor(() => {
      expect(titles.result.current.data?.map((t) => t.code)).toEqual([
        'gynaecologist',
        'purchasing',
        'other',
      ]);
    });
  });

  it('mutations send If-Match and invalidate the list and the detail', async () => {
    const seen: { method: string; ifMatch: string | null; path: string }[] = [];
    server.use(
      http.patch(`${API_V1}/accounts/:id`, ({ request }) => {
        seen.push({
          method: 'PATCH',
          ifMatch: request.headers.get('if-match'),
          path: new URL(request.url).pathname,
        });
        return HttpResponse.json({ ...tambre, version: 4 });
      }),
      http.put(`${API_V1}/accounts/:id/assignment`, ({ request }) => {
        seen.push({
          method: 'PUT',
          ifMatch: request.headers.get('if-match'),
          path: new URL(request.url).pathname,
        });
        return HttpResponse.json({ ...tambre, version: 4 });
      }),
      http.put(`${API_V1}/accounts/:id/addresses`, ({ request }) => {
        seen.push({
          method: 'PUT',
          ifMatch: request.headers.get('if-match'),
          path: new URL(request.url).pathname,
        });
        return HttpResponse.json({ ...tambre, version: 4 });
      }),
    );
    const { Wrapper, queryClient } = wrapperFor();
    queryClient.setQueryData(['accounts', 'detail', tambre.id], tambre);
    queryClient.setQueryData(['accounts', 'list', {}], { items: [], total: 0 });

    const update = renderHook(() => useUpdateAccount(), { wrapper: Wrapper });
    const assign = renderHook(() => useAssignAccount(), { wrapper: Wrapper });
    const addresses = renderHook(() => useReplaceAddresses(), { wrapper: Wrapper });
    const create = renderHook(() => useCreateAccount(), { wrapper: Wrapper });

    await update.result.current.mutateAsync({
      id: tambre.id,
      version: 3,
      payload: { city: 'Madrid' },
    });
    await assign.result.current.mutateAsync({
      id: tambre.id,
      version: 3,
      payload: { owner_id: null },
    });
    await addresses.result.current.mutateAsync({ id: tambre.id, version: 3, addresses: [] });
    const created = await create.result.current.mutateAsync({
      name: 'Nuevo',
      account_type_id: accounts[0]!.account_type_id,
      province_code: '28',
    });

    expect(created.id).toBe('new-account-id');
    expect(seen.map((s) => s.ifMatch)).toEqual(['"3"', '"3"', '"3"']);
    expect(
      seen.map((s) => s.path.endsWith('/assignment') || s.path.endsWith('/addresses')),
    ).toEqual([false, true, true]);
    expect(queryClient.getQueryState(['accounts', 'detail', tambre.id])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(['accounts', 'list', {}])?.isInvalidated).toBe(true);
  });
});
