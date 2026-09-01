import { Bell } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Button } from '@/components/ui/button';

import { useNotifications } from '../queries';

/**
 * The bell announces, the block on Hoy explains.
 *
 * Activating it goes to `/hoy` instead of opening a second list, so the same information
 * never lives in two places that can disagree. The count is in the accessible name, never
 * only in the badge: a number conveyed by colour alone says nothing to a screen reader.
 */
export function NotificationsBell() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const inbox = useNotifications();
  const unread = inbox.data?.unread_count ?? 0;

  return (
    <Button
      variant="ghost"
      size="icon"
      className="relative min-h-touch min-w-touch"
      aria-label={
        unread > 0
          ? t('activities:notifications.bell', { count: unread })
          : t('activities:notifications.bellEmpty')
      }
      onClick={() => {
        navigate(routes.today);
      }}
    >
      <Bell className="size-5" aria-hidden="true" />
      {unread > 0 ? (
        <span
          aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 flex size-5 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground"
        >
          {unread > 9 ? '9+' : unread}
        </span>
      ) : null}
    </Button>
  );
}
