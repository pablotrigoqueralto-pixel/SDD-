import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAccount, useIsManager, useIsStaff } from '@/features/accounts';
import { useActivityTypes } from '@/features/reference';

import type { ActivityStatus } from '../api';
import { ActivityCard } from '../components/ActivityCard';
import { useTimeline } from '../queries';

const PAGE_SIZE = 25;
const STATUSES: ActivityStatus[] = ['planned', 'done', 'cancelled'];

/** /centros/:id/actividades — the full timeline with filters and pagination. */
export function TimelinePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { accountId } = useParams<{ accountId: string }>();
  const [params, setParams] = useSearchParams();
  const isStaff = useIsStaff();
  const isManager = useIsManager();
  const account = useAccount(accountId);
  const types = useActivityTypes();
  const page = Number(params.get('page') ?? '1');
  const filters = {
    activity_type_id: params.get('activity_type_id') ?? '',
    status: (params.get('status') ?? '') as ActivityStatus | '',
    page,
    page_size: PAGE_SIZE,
  };
  const timeline = useTimeline(accountId, filters);
  const canWrite = !isStaff || isManager;

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next, { replace: true });
  };

  const newButton = canWrite ? (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.activityNew(accountId ?? ''));
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('activities:new')}
    </Button>
  ) : null;

  const total = timeline.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageLabel = `${page} / ${pageCount}`;

  return (
    <>
      <PageHeader
        title={
          account.data ? `${t('activities:title')} · ${account.data.name}` : t('activities:title')
        }
        backTo={routes.account(accountId ?? '')}
        action={newButton}
      />
      <div className="flex flex-col gap-3 py-3 lg:flex-row">
        <NativeSelect
          aria-label={t('activities:timeline.filterType')}
          value={filters.activity_type_id}
          onChange={(event) => {
            setParam('activity_type_id', event.target.value);
          }}
          className="lg:w-56"
        >
          <option value="">{t('activities:timeline.allTypes')}</option>
          {types.data?.map((type) => (
            <option key={type.id} value={type.id}>
              {type.name_es}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect
          aria-label={t('activities:timeline.filterStatus')}
          value={filters.status}
          onChange={(event) => {
            setParam('status', event.target.value);
          }}
          className="lg:w-56"
        >
          <option value="">{t('activities:timeline.allStatuses')}</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {t(`activities:status.${status}`)}
            </option>
          ))}
        </NativeSelect>
      </div>
      {timeline.isPending ? (
        <div role="status" aria-busy="true" aria-label={t('app.loading')}>
          <Skeleton className="h-16 w-full" />
        </div>
      ) : timeline.isError ? (
        <ErrorState error={timeline.error} onRetry={() => void timeline.refetch()} />
      ) : timeline.data.items.length === 0 ? (
        <EmptyState title={t('activities:empty')} action={newButton} />
      ) : (
        <ul className="flex flex-col gap-2">
          {timeline.data.items.map((entry) => (
            <li key={entry.id}>
              <ActivityCard activity={entry.activity} withCancel={canWrite} />
            </li>
          ))}
        </ul>
      )}
      {pageCount > 1 ? (
        <nav
          className="flex items-center justify-end gap-2 py-3"
          aria-label={t('activities:title')}
        >
          <Button
            variant="outline"
            size="sm"
            aria-label={t('actions.back')}
            disabled={page <= 1}
            onClick={() => {
              setParam('page', String(page - 1));
            }}
          >
            <ChevronLeft className="size-4" aria-hidden="true" />
          </Button>
          <span className="text-sm text-muted-foreground">{pageLabel}</span>
          <Button
            variant="outline"
            size="sm"
            aria-label={t('actions.loadMore')}
            disabled={page >= pageCount}
            onClick={() => {
              setParam('page', String(page + 1));
            }}
          >
            <ChevronRight className="size-4" aria-hidden="true" />
          </Button>
        </nav>
      ) : null}
      <Outlet />
    </>
  );
}
