import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { ana, tambre } from '@/test/msw/accounts-fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { createTestQueryClient } from '@/test/render';

import {
  useAccountContacts,
  useAnonymiseContact,
  useContact,
  useCreateContact,
  useUpdateContact,
} from './queries';

function wrapperFor(queryClient = createTestQueryClient()) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { Wrapper, queryClient };
}

describe('contact queries', () => {
  it('lists the contacts of an account (primary first) and reads one contact', async () => {
    const { Wrapper } = wrapperFor();

    const list = renderHook(() => useAccountContacts(tambre.id), { wrapper: Wrapper });
    const detail = renderHook(() => useContact(ana.id), { wrapper: Wrapper });

    await waitFor(() => {
      expect(list.result.current.data?.map((c) => c.first_name)).toEqual(['Ana', 'Bea']);
    });
    await waitFor(() => {
      expect(detail.result.current.data?.account_name).toBe('Clínica Tambre');
    });
  });

  it('passes include_inactive only when requested', async () => {
    let url: URL | null = null;
    server.use(
      http.get(`${API_V1}/accounts/:id/contacts`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json([]);
      }),
    );
    const { Wrapper } = wrapperFor();

    const { result } = renderHook(() => useAccountContacts(tambre.id, true), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(url!.searchParams.get('include_inactive')).toBe('true');
  });

  it('mutations send If-Match and invalidate the account detail, list and contacts', async () => {
    const headers: (string | null)[] = [];
    server.use(
      http.patch(`${API_V1}/contacts/:id`, ({ request }) => {
        headers.push(request.headers.get('if-match'));
        return HttpResponse.json({ ...ana, version: 2 });
      }),
      http.post(`${API_V1}/contacts/:id/anonymise`, ({ request }) => {
        headers.push(request.headers.get('if-match'));
        return HttpResponse.json({ ...ana, first_name: 'Contacto', version: 3 });
      }),
    );
    const { Wrapper, queryClient } = wrapperFor();
    queryClient.setQueryData(['accounts', 'detail', tambre.id], tambre);
    queryClient.setQueryData(['contacts', 'account', tambre.id, { includeInactive: false }], []);

    const create = renderHook(() => useCreateContact(), { wrapper: Wrapper });
    const update = renderHook(() => useUpdateContact(), { wrapper: Wrapper });
    const anonymise = renderHook(() => useAnonymiseContact(), { wrapper: Wrapper });

    const created = await create.result.current.mutateAsync({
      accountId: tambre.id,
      payload: { first_name: 'Nuevo', last_name: 'Contacto', is_primary: false },
    });
    await update.result.current.mutateAsync({
      id: ana.id,
      accountId: tambre.id,
      version: 1,
      payload: { notes: 'x' },
    });
    const anonymised = await anonymise.result.current.mutateAsync({
      id: ana.id,
      accountId: tambre.id,
      version: 2,
    });

    expect(created.id).toBe('new-contact-id');
    expect(anonymised.first_name).toBe('Contacto');
    expect(headers).toEqual(['"1"', '"2"']);
    expect(queryClient.getQueryState(['accounts', 'detail', tambre.id])?.isInvalidated).toBe(true);
    expect(
      queryClient.getQueryState(['contacts', 'account', tambre.id, { includeInactive: false }])
        ?.isInvalidated,
    ).toBe(true);
  });
});
