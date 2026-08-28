import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { tambre } from '@/test/msw/accounts-fixtures';
import { callPlanned, OVERDUE_ID, visitDone } from '@/test/msw/activities-fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { createTestQueryClient } from '@/test/render';

import {
  useCancelActivity,
  useCompleteActivity,
  useCreateActivity,
  useRescheduleActivity,
  useTimeline,
  useToday,
  useUpdateActivity,
} from './queries';

function wrapperFor(queryClient = createTestQueryClient()) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return { Wrapper, queryClient };
}

describe('activity queries', () => {
  it('reads the timeline with filters and the day (optionally for another user)', async () => {
    const seen: string[] = [];
    server.use(
      http.get(`${API_V1}/me/today`, ({ request }) => {
        seen.push(new URL(request.url).searchParams.get('user_id') ?? 'me');
        return HttpResponse.json({
          date: '2026-08-28',
          today: [],
          overdue: [],
          week: { done_by_type: {}, planned_remaining: 0 },
        });
      }),
    );
    const { Wrapper } = wrapperFor();

    const timeline = renderHook(() => useTimeline(tambre.id, { status: 'planned', page_size: 5 }), {
      wrapper: Wrapper,
    });
    const mine = renderHook(() => useToday(), { wrapper: Wrapper });
    const theirs = renderHook(() => useToday('rep-2'), { wrapper: Wrapper });

    await waitFor(() => {
      expect(timeline.result.current.data?.items.map((e) => e.id)).toEqual([
        callPlanned.id,
        OVERDUE_ID,
      ]);
    });
    await waitFor(() => {
      expect(mine.result.current.isSuccess && theirs.result.current.isSuccess).toBe(true);
    });
    expect(seen.sort()).toEqual(['me', 'rep-2']);
  });

  it('mutations send If-Match and invalidate today, the timeline and the account', async () => {
    const headers: (string | null)[] = [];
    const record = ({ request }: { request: Request }) => {
      headers.push(request.headers.get('if-match'));
      return HttpResponse.json({ ...callPlanned, version: 2 });
    };
    server.use(
      http.patch(`${API_V1}/activities/:id`, record),
      http.post(`${API_V1}/activities/:id/complete`, record),
      http.post(`${API_V1}/activities/:id/cancel`, record),
      http.post(`${API_V1}/activities/:id/reschedule`, record),
    );
    const { Wrapper, queryClient } = wrapperFor();
    queryClient.setQueryData(['activities', 'today', 'me'], {});
    queryClient.setQueryData(['activities', 'timeline', tambre.id, {}], {});
    queryClient.setQueryData(['accounts', 'detail', tambre.id], tambre);
    queryClient.setQueryData(['accounts', 'list', {}], {});
    const base = { id: callPlanned.id, accountId: tambre.id, version: 1 };

    const create = renderHook(() => useCreateActivity(), { wrapper: Wrapper });
    const update = renderHook(() => useUpdateActivity(), { wrapper: Wrapper });
    const complete = renderHook(() => useCompleteActivity(), { wrapper: Wrapper });
    const cancel = renderHook(() => useCancelActivity(), { wrapper: Wrapper });
    const reschedule = renderHook(() => useRescheduleActivity(), { wrapper: Wrapper });

    const created = await create.result.current.mutateAsync({
      account_id: tambre.id,
      activity_type_id: visitDone.activity_type_id,
      status: 'done',
    });
    await update.result.current.mutateAsync({ ...base, payload: { subject: 'x' } });
    await complete.result.current.mutateAsync({ ...base, payload: { outcome: 'positive' } });
    await cancel.result.current.mutateAsync({ ...base, reason: 'closed' });
    await reschedule.result.current.mutateAsync({ ...base, scheduledAt: '2026-09-01T10:00:00Z' });

    expect(created.id).toBe('new-activity-id');
    expect(headers).toEqual(['"1"', '"1"', '"1"', '"1"']);
    for (const key of [
      ['activities', 'today', 'me'],
      ['activities', 'timeline', tambre.id, {}],
      ['accounts', 'detail', tambre.id],
      ['accounts', 'list', {}],
    ]) {
      expect(queryClient.getQueryState(key)?.isInvalidated, JSON.stringify(key)).toBe(true);
    }
  });
});
