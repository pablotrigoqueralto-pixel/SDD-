import { FileText, GitBranch } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';

import type { TimelineEntryRead } from '../api';
import { ActivityCard, formatWhen } from './ActivityCard';

interface TimelineEntryItemProps {
  entry: TimelineEntryRead;
  canWrite: boolean;
}

/** One timeline row: an activity card, a stage line, or a quote event line. */
export function TimelineEntryItem({ entry, canWrite }: TimelineEntryItemProps) {
  const { t } = useTranslation();
  if (entry.kind === 'activity' && entry.activity) {
    return <ActivityCard activity={entry.activity} withCancel={canWrite} />;
  }
  if (entry.quote_event) {
    const event = entry.quote_event;
    return (
      <div className="flex items-start gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
        <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            <Link to={routes.quote(event.quote_id)} className="underline">
              {entry.title}
            </Link>
          </p>
          <p className="text-muted-foreground">
            <Link to={routes.opportunity(event.opportunity_id)} className="underline">
              {event.opportunity_name}
            </Link>
            {' · '}
            {formatWhen(entry.occurred_at, 'both')}
          </p>
        </div>
      </div>
    );
  }
  if (!entry.stage_change) {
    return <p className="text-sm text-muted-foreground">{entry.title}</p>;
  }
  const change = entry.stage_change;
  return (
    <div className="flex items-start gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
      <GitBranch className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{entry.title}</p>
        <p className="text-muted-foreground">
          <Link to={routes.opportunity(change.opportunity_id)} className="underline">
            {change.opportunity_name}
          </Link>
          {' · '}
          {formatWhen(entry.occurred_at, 'both')}
          {change.actor_name ? (
            <>
              {' · '}
              {t('activities:timeline.by', { name: change.actor_name })}
            </>
          ) : null}
        </p>
      </div>
    </div>
  );
}
