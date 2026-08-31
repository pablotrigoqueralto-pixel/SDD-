import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Skeleton } from '@/components/ui/skeleton';
import { useSessionStore } from '@/features/auth';
import { formatPrice } from '@/features/catalogue';

import { useDashboard } from '../queries';

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <span className="truncate text-xs text-muted-foreground">{label}</span>
      <span className="truncate text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}

/** Current-month key figures on Hoy for management; renders nothing for other roles or on error. */
export function DashboardTeaser() {
  const { t } = useTranslation();
  const role = useSessionStore((state) => state.user?.role);
  const isManagement = role === 'sales_manager' || role === 'admin';
  const query = useDashboard('month');

  if (!isManagement) return null;
  if (query.isError) return null;
  if (query.isPending) return <Skeleton className="h-16 w-full" />;

  const { summary } = query.data;
  return (
    <Link
      to={routes.reports}
      aria-label={t('dashboard:teaser.title')}
      className="flex items-center gap-3 rounded-lg border bg-card p-3 hover:bg-muted"
    >
      <Figure label={t('dashboard:kpis.won')} value={formatPrice(summary.won.amount)} />
      <Figure label={t('dashboard:kpis.forecast')} value={formatPrice(summary.forecast.amount)} />
      <Figure
        label={t('dashboard:kpis.openPipeline')}
        value={formatPrice(summary.open_pipeline.amount)}
      />
      <span className="shrink-0 text-sm font-medium text-primary">
        {t('dashboard:teaser.link')}
      </span>
    </Link>
  );
}
