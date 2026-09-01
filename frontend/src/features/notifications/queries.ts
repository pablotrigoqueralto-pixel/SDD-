import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notifications,
} from './api';

export const notificationKeys = {
  all: ['notifications'] as const,
  inbox: () => [...notificationKeys.all, 'inbox'] as const,
};

/**
 * One request feeds the bell and the block, so they cannot disagree.
 *
 * It refetches when the window regains focus rather than on a timer: the case to serve is
 * "I come back to the CRM and see what happened", not a badge ticking while nobody looks.
 */
export function useNotifications() {
  return useQuery({
    queryKey: notificationKeys.inbox(),
    queryFn: getNotifications,
    refetchOnWindowFocus: true,
    // No stale window: coming back to the tab is exactly when the count must be right,
    // and the request is one small row count.
    staleTime: 0,
  });
}

function useReplaceInbox() {
  const queryClient = useQueryClient();
  return (data: Notifications) => {
    queryClient.setQueryData(notificationKeys.inbox(), data);
  };
}

export function useMarkNotificationRead() {
  const replace = useReplaceInbox();
  return useMutation({
    mutationFn: (id: string) => markNotificationRead(id),
    onSuccess: replace,
    meta: { silent: true },
  });
}

export function useMarkAllNotificationsRead() {
  const replace = useReplaceInbox();
  return useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: replace,
    meta: { silent: true },
  });
}
