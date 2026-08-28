import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

import { useTimeline } from '../queries';
import { TimelineEntryItem } from './TimelineEntryItem';

const PREVIEW_SIZE = 5;

interface TimelineSectionProps {
  accountId: string;
  canWrite: boolean;
}

/** The five most recent timeline entries of the 360º page, with "Ver todas". */
export function TimelineSection({ accountId, canWrite }: TimelineSectionProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const timeline = useTimeline(accountId, { page_size: PREVIEW_SIZE });

  if (timeline.isPending) return <Skeleton className="h-16 w-full" />;
  if (timeline.isError) {
    return <ErrorState error={timeline.error} onRetry={() => void timeline.refetch()} />;
  }
  const { items, total } = timeline.data;
  const seeAllLabel = `${t('activities:seeAll')} (${total})`;
  return (
    <div className="flex flex-col gap-2">
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('activities:empty')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((entry) => (
            <li key={entry.id}>
              <TimelineEntryItem entry={entry} canWrite={canWrite} />
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {total > items.length ? (
          <Link to={routes.timeline(accountId)} className="text-sm underline">
            {seeAllLabel}
          </Link>
        ) : (
          <span />
        )}
        {canWrite ? (
          <Button
            variant="outline"
            size="sm"
            className="min-h-touch"
            onClick={() => {
              navigate(routes.activityNew(accountId));
            }}
          >
            <Plus className="size-4" aria-hidden="true" />
            {t('activities:new')}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
