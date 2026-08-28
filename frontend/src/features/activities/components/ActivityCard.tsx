import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/badge';
import { useActivityTypes } from '@/features/reference';

import type { ActivityRead } from '../api';
import { ActivityActions } from './ActivityActions';
import { ActivityTypeIcon } from './ActivityTypeIcon';

const DATE = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' });
const TIME = new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' });

export function formatWhen(iso: string, variant: 'date' | 'time' | 'both' = 'both'): string {
  const date = new Date(iso);
  if (variant === 'time') return TIME.format(date);
  if (variant === 'date') return DATE.format(date);
  return `${DATE.format(date)} · ${TIME.format(date)}`;
}

interface ActivityCardProps {
  activity: ActivityRead;
  /** Show the centre name (Hoy) or hide it (inside the account page). */
  showAccount?: boolean;
  /** Time only (Hoy list) or date and time (timeline). */
  whenVariant?: 'time' | 'both';
  withCancel?: boolean;
  /** Opens the detail sheet route when tapping the title. */
  linkToDetail?: boolean;
}

export function ActivityCard({
  activity,
  showAccount = false,
  whenVariant = 'both',
  withCancel = false,
  linkToDetail = true,
}: ActivityCardProps) {
  const { t } = useTranslation();
  const types = useActivityTypes();
  const type = types.data?.find((candidate) => candidate.id === activity.activity_type_id);
  const title = activity.subject ?? activity.activity_type_name;
  const contacts = activity.contacts.map((contact) => contact.name).join(', ');
  const when = formatWhen(
    activity.status === 'done' && activity.done_at ? activity.done_at : activity.scheduled_at,
    whenVariant,
  );

  return (
    <article className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-primary">
          <ActivityTypeIcon icon={type?.icon} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">{when}</span>
            {activity.status === 'cancelled' ? (
              <Badge variant="outline">{t('activities:status.cancelled')}</Badge>
            ) : null}
            {activity.status === 'planned' ? (
              <Badge variant="secondary">{t('activities:status.planned')}</Badge>
            ) : null}
            {activity.outcome ? (
              <Badge variant={activity.outcome === 'negative' ? 'destructive' : 'default'}>
                {t(`activities:outcome.${activity.outcome}`)}
              </Badge>
            ) : null}
          </div>
          {linkToDetail ? (
            <Link
              to={routes.activity(activity.account_id, activity.id)}
              className="block truncate font-medium underline-offset-2 hover:underline"
            >
              {title}
            </Link>
          ) : (
            <p className="truncate font-medium">{title}</p>
          )}
          {showAccount ? (
            <Link
              to={routes.account(activity.account_id)}
              className="block truncate text-sm text-muted-foreground hover:underline"
            >
              {activity.account_name}
            </Link>
          ) : null}
          <p className="text-xs text-muted-foreground">
            {t('activities:timeline.by', { name: activity.owner_name })}
            {contacts ? ` · ${t('activities:timeline.with', { names: contacts })}` : ''}
          </p>
        </div>
      </div>
      <ActivityActions activity={activity} withCancel={withCancel} />
    </article>
  );
}
