import { Plus } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useIsStaff } from '@/features/accounts';
import { useUsers } from '@/features/admin';
import { useSessionStore } from '@/features/auth';
import { useActivityTypes } from '@/features/reference';

import type { TodayRead } from '../api';
import { ActivityCard } from '../components/ActivityCard';
import { useToday } from '../queries';

const DAY = new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });

function WeekSummary({ week }: { week: TodayRead['week'] }) {
  const { t } = useTranslation();
  const types = useActivityTypes();
  const parts = Object.entries(week.done_by_type)
    .filter(([, count]) => count > 0)
    .map(([typeId, count]) => {
      const name = types.data?.find((type) => type.id === typeId)?.name_es ?? '';
      return `${count} ${name.toLocaleLowerCase()}`;
    });
  const done = parts.length > 0 ? parts.join(' · ') : t('activities:today.nothingDone');
  return (
    <p className="rounded-md bg-muted px-3 py-2 text-sm">
      <span className="font-medium">{t('activities:today.week')}</span>
      {': '}
      {t('activities:today.weekSummary', { done, remaining: week.planned_remaining })}
    </p>
  );
}

function TodayLists({ data }: { data: TodayRead }) {
  const { t } = useTranslation();
  const overdueTitle = `${t('activities:today.overdue')} (${data.overdue.length})`;
  const plannedTitle = `${t('activities:today.planned')} (${data.today.length})`;
  return (
    <>
      <WeekSummary week={data.week} />
      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="today-overdue">
          <h2 id="today-overdue" className="mb-2 font-semibold text-destructive">
            {overdueTitle}
          </h2>
          {data.overdue.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('activities:today.noOverdue')}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {data.overdue.map((activity) => (
                <li key={activity.id}>
                  <ActivityCard activity={activity} showAccount whenVariant="both" />
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-labelledby="today-planned">
          <h2 id="today-planned" className="mb-2 font-semibold">
            {plannedTitle}
          </h2>
          {data.today.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('activities:today.nothingPlanned')}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {data.today.map((activity) => (
                <li key={activity.id}>
                  <ActivityCard activity={activity} showAccount whenVariant="time" />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}

/** The rep's day: overdue first, then today's plan, with one-tap actions. */
export function TodayPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useSessionStore((state) => state.user);
  const isStaff = useIsStaff();
  const [repId, setRepId] = useState('');
  const reps = useUsers({ role: 'sales_rep', is_active: 'true', page_size: 200 });
  const today = useToday(repId || undefined);
  const withoutScope =
    user?.role === 'sales_rep' &&
    (user.territory_ids.length === 0 || user.division_ids.length === 0);
  const canAct = user?.role !== 'back_office';

  const newButton = canAct ? (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.todayNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('activities:new')}
    </Button>
  ) : null;

  return (
    <>
      <PageHeader title={`${t('today.title')} · ${DAY.format(new Date())}`} action={newButton} />
      <div className="flex flex-col gap-3 py-3">
        {withoutScope ? (
          <p role="note" className="rounded-md bg-accent px-3 py-2 text-sm text-accent-foreground">
            {t('auth:scopeWarning')}
          </p>
        ) : null}
        {isStaff ? (
          <NativeSelect
            aria-label={t('activities:today.rep')}
            value={repId}
            onChange={(event) => {
              setRepId(event.target.value);
            }}
            className="lg:w-64"
          >
            <option value="">{t('activities:today.me')}</option>
            {reps.data?.items.map((rep) => (
              <option key={rep.id} value={rep.id}>
                {rep.full_name}
              </option>
            ))}
          </NativeSelect>
        ) : null}
        {today.isPending ? (
          <div role="status" aria-busy="true" aria-label={t('app.loading')}>
            <Skeleton className="h-24 w-full" />
          </div>
        ) : today.isError ? (
          <ErrorState error={today.error} onRetry={() => void today.refetch()} />
        ) : (
          <TodayLists data={today.data} />
        )}
      </div>
      <Outlet />
    </>
  );
}
