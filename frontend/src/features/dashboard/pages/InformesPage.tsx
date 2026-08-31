import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { Skeleton } from '@/components/ui/skeleton';

import type { DashboardPeriod } from '../api';
import { ActivitySection, NeglectedSection } from '../components/ActivitySections';
import { BreakdownSection, StageSection } from '../components/BarSections';
import { KpiCards } from '../components/KpiCards';
import { PeriodSelector } from '../components/PeriodSelector';
import { useDashboard } from '../queries';

/** Informes: the whole panel from one request; mobile stacks, lg: two columns. */
export function InformesPage() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<DashboardPeriod>('month');
  const query = useDashboard(period);

  return (
    <>
      <PageHeader title={t('dashboard:title')} />
      <div className="flex flex-col gap-4 py-4">
        <PeriodSelector value={period} onChange={setPeriod} />
        {query.isPending ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : query.isError ? (
          <ErrorState
            error={query.error}
            onRetry={() => {
              void query.refetch();
            }}
          />
        ) : (
          <div className="flex flex-col gap-4">
            <KpiCards summary={query.data.summary} />
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="flex flex-col gap-4">
                <StageSection rows={query.data.pipeline_by_stage} />
                <BreakdownSection
                  title={t('dashboard:sections.divisions')}
                  rows={query.data.by_division}
                />
              </div>
              <div className="flex flex-col gap-4">
                {query.data.by_rep ? (
                  <BreakdownSection title={t('dashboard:sections.reps')} rows={query.data.by_rep} />
                ) : null}
                <ActivitySection rows={query.data.activity} />
              </div>
            </div>
            <NeglectedSection data={query.data.neglected_accounts} />
          </div>
        )}
      </div>
    </>
  );
}
