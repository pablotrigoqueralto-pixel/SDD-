import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { Providers, createQueryClient } from '@/app/providers';
import { API_V1 } from '@/test/msw/handlers';
import { referenceBundle } from '@/test/msw/reference-fixtures';
import { server } from '@/test/msw/server';

import { labelOf, useAccountTypes, useBrands, useDivisions, usePipelines } from './queries';

describe('reference data hooks', () => {
  it('shares a single request between selectors', async () => {
    let requests = 0;
    server.use(
      http.get(`${API_V1}/reference-data`, () => {
        requests += 1;
        return HttpResponse.json(referenceBundle);
      }),
    );
    const queryClient = createQueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Providers queryClient={queryClient}>{children}</Providers>
    );

    const { result } = renderHook(
      () => ({
        types: useAccountTypes(),
        brands: useBrands(),
        divisions: useDivisions(),
        pipelines: usePipelines(),
      }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.pipelines.isSuccess).toBe(true);
    });
    expect(requests).toBe(1);
    expect(result.current.types.data?.map((t) => t.code)).toEqual([
      'ivf_clinic',
      'public_hospital',
    ]);
    expect(result.current.brands.data?.length).toBe(3);
    expect(result.current.divisions.data?.length).toBe(2);
    expect(result.current.pipelines.data?.[0]?.stages[0]?.code).toBe('contact');
  });

  it('labelOf resolves names and falls back to the id', () => {
    const items = [{ id: 'a', name: 'Alpha' }];

    expect(labelOf(items, 'a', (i) => i.name)).toBe('Alpha');
    expect(labelOf(items, 'zzz', (i) => i.name)).toBe('zzz');
    expect(labelOf(items, null, (i) => i.name)).toBe('');
    expect(labelOf(undefined, 'a', (i: { id: string; name: string }) => i.name)).toBe('a');
  });
});
