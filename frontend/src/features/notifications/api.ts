import { apiClient } from '@/api/client';
import type { components } from '@/api/schema';

export type Notifications = components['schemas']['NotificationsRead'];
export type Notification = components['schemas']['NotificationRead'];
export type NotificationKind = components['schemas']['NotificationKind'];

export async function getNotifications(): Promise<Notifications> {
  const { data } = await apiClient.get<Notifications>('/notifications');
  return data;
}

export async function markNotificationRead(id: string): Promise<Notifications> {
  const { data } = await apiClient.post<Notifications>(`/notifications/${id}/read`);
  return data;
}

export async function markAllNotificationsRead(): Promise<Notifications> {
  const { data } = await apiClient.post<Notifications>('/notifications/read-all');
  return data;
}
