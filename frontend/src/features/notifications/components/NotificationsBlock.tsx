import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Button } from '@/components/ui/button';

import type { Notification } from '../api';
import { useMarkAllNotificationsRead, useMarkNotificationRead, useNotifications } from '../queries';

function payloadString(notification: Notification, key: string): string {
  const value: unknown = notification.payload[key];
  return typeof value === 'string' ? value : '';
}

/** Where a notice takes you: the thing somebody put on your plate. */
function destination(notification: Notification): string | null {
  const id = notification.entity_id;
  if (!id) return null;
  if (notification.entity_type === 'account') return routes.account(id);
  if (notification.entity_type === 'opportunity') return routes.opportunity(id);
  return null;
}

/**
 * What somebody else put on your plate, above the day's own lists.
 *
 * Absent entirely when nothing is unread: an empty inbox is not news, so it gets no empty
 * state either.
 */
export function NotificationsBlock() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const inbox = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();
  const items = inbox.data?.items ?? [];

  if (items.length === 0) return null;

  const open = (notification: Notification) => {
    markRead.mutate(notification.id);
    const to = destination(notification);
    if (to) navigate(to);
  };

  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-muted/30 p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{t('activities:notifications.title')}</h2>
        <Button
          variant="ghost"
          size="sm"
          className="min-h-touch"
          onClick={() => {
            markAll.mutate();
          }}
        >
          {t('activities:notifications.markAll')}
        </Button>
      </div>
      <ul className="flex flex-col gap-1" aria-label={t('activities:notifications.title')}>
        {items.map((notification) => (
          <li key={notification.id}>
            <button
              type="button"
              className="min-h-touch w-full rounded-md px-2 py-1 text-left text-sm hover:bg-accent"
              onClick={() => {
                open(notification);
              }}
            >
              {t(`activities:notifications.kinds.${notification.kind}`, {
                actor: notification.actor_name ?? t('activities:notifications.someone'),
                account: payloadString(notification, 'account_name'),
                name: payloadString(notification, 'name'),
              })}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
