import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { accountKeys, activityKeys } from '@/api/query-keys';

import {
  cancelActivity,
  listAccountOpportunityOptions,
  listActivities,
  completeActivity,
  createActivity,
  getActivity,
  getTimeline,
  getToday,
  rescheduleActivity,
  updateActivity,
  type ActivityComplete,
  type ActivityCreate,
  type ActivityUpdate,
  type ActivityListFilters,
  type TimelineFilters,
} from './api';

export function useTimeline(accountId: string | undefined, filters: TimelineFilters = {}) {
  return useQuery({
    queryKey: activityKeys.timeline(accountId ?? '', filters as Record<string, unknown>),
    queryFn: () => getTimeline(accountId ?? '', filters),
    enabled: Boolean(accountId),
    placeholderData: (previous) => previous,
  });
}

export function useToday(userId?: string) {
  return useQuery({
    queryKey: activityKeys.today(userId ?? 'me'),
    queryFn: () => getToday(userId),
    staleTime: 60_000,
  });
}

export function useActivities(filters: ActivityListFilters) {
  return useQuery({
    queryKey: [...activityKeys.all, 'list', filters] as const,
    queryFn: () => listActivities(filters),
    placeholderData: (previous) => previous,
  });
}

export function useAccountOpportunityOptions(accountId: string | undefined) {
  return useQuery({
    queryKey: [...activityKeys.all, 'opportunity-options', accountId ?? ''] as const,
    queryFn: () => listAccountOpportunityOptions(accountId ?? ''),
    enabled: Boolean(accountId),
  });
}

export function useActivity(id: string | undefined) {
  return useQuery({
    queryKey: activityKeys.detail(id ?? ''),
    queryFn: () => getActivity(id ?? ''),
    enabled: Boolean(id),
  });
}

/** Any activity change moves "Hoy", the timeline and the account's recency columns. */
function useInvalidateActivities() {
  const queryClient = useQueryClient();
  return async (accountId: string, activityId?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: activityKeys.todays() }),
      queryClient.invalidateQueries({ queryKey: activityKeys.timelines(accountId) }),
      queryClient.invalidateQueries({ queryKey: accountKeys.detail(accountId) }),
      queryClient.invalidateQueries({ queryKey: accountKeys.lists() }),
      activityId
        ? queryClient.invalidateQueries({ queryKey: activityKeys.detail(activityId) })
        : Promise.resolve(),
    ]);
  };
}

export function useCreateActivity() {
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: (payload: ActivityCreate) => createActivity(payload),
    onSuccess: (_data, payload) => invalidate(payload.account_id),
    meta: { silent: true },
  });
}

interface Versioned {
  id: string;
  accountId: string;
  version: number;
}

export function useUpdateActivity() {
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: ({ id, version, payload }: Versioned & { payload: ActivityUpdate }) =>
      updateActivity(id, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useCompleteActivity() {
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: ({ id, version, payload }: Versioned & { payload: ActivityComplete }) =>
      completeActivity(id, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useCancelActivity() {
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: ({ id, version, reason }: Versioned & { reason: string }) =>
      cancelActivity(id, version, reason),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useRescheduleActivity() {
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: ({ id, version, scheduledAt }: Versioned & { scheduledAt: string }) =>
      rescheduleActivity(id, version, scheduledAt),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}
