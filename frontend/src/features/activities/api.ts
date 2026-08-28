import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type ActivityRead = components['schemas']['ActivityRead'];
export type ActivityCreate = components['schemas']['ActivityCreate'];
export type ActivityUpdate = components['schemas']['ActivityUpdate'];
export type ActivityComplete = components['schemas']['ActivityComplete'];
export type ActivityStatus = components['schemas']['ActivityStatus'];
export type ActivityOutcome = components['schemas']['ActivityOutcome'];
export type NextActionWrite = components['schemas']['NextActionWrite'];
export type TimelineEntryRead = components['schemas']['TimelineEntryRead'];
export type TimelinePage = components['schemas']['Page_TimelineEntryRead_'];
export type TodayRead = components['schemas']['TodayRead'];

export interface TimelineFilters {
  activity_type_id?: string;
  status?: ActivityStatus | '';
  page?: number;
  page_size?: number;
}

export async function getTimeline(
  accountId: string,
  filters: TimelineFilters = {},
): Promise<TimelinePage> {
  const params: Record<string, string | number> = {};
  if (filters.activity_type_id) params.activity_type_id = filters.activity_type_id;
  if (filters.status) params.status = filters.status;
  if (filters.page) params.page = filters.page;
  if (filters.page_size) params.page_size = filters.page_size;
  const { data } = await apiClient.get<TimelinePage>(`/accounts/${accountId}/timeline`, {
    params,
  });
  return data;
}

export async function getToday(userId?: string): Promise<TodayRead> {
  const { data } = await apiClient.get<TodayRead>('/me/today', {
    params: userId ? { user_id: userId } : {},
  });
  return data;
}

export async function getActivity(id: string): Promise<ActivityRead> {
  const { data } = await apiClient.get<ActivityRead>(`/activities/${id}`);
  return data;
}

export async function createActivity(payload: ActivityCreate): Promise<ActivityRead> {
  const { data } = await apiClient.post<ActivityRead>('/activities', payload);
  return data;
}

export async function updateActivity(
  id: string,
  version: number,
  payload: ActivityUpdate,
): Promise<ActivityRead> {
  const { data } = await apiClient.patch<ActivityRead>(`/activities/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function completeActivity(
  id: string,
  version: number,
  payload: ActivityComplete,
): Promise<ActivityRead> {
  const { data } = await apiClient.post<ActivityRead>(`/activities/${id}/complete`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function cancelActivity(
  id: string,
  version: number,
  reason: string,
): Promise<ActivityRead> {
  const { data } = await apiClient.post<ActivityRead>(
    `/activities/${id}/cancel`,
    { reason },
    { headers: ifMatch(version) },
  );
  return data;
}

export async function rescheduleActivity(
  id: string,
  version: number,
  scheduledAt: string,
): Promise<ActivityRead> {
  const { data } = await apiClient.post<ActivityRead>(
    `/activities/${id}/reschedule`,
    { scheduled_at: scheduledAt },
    { headers: ifMatch(version) },
  );
  return data;
}
