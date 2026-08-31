import { useTranslation } from 'react-i18next';

import { cn } from '@/lib/cn';

import type { DashboardPeriod } from '../api';

const PERIODS: DashboardPeriod[] = ['month', 'quarter', 'year'];

interface PeriodSelectorProps {
  value: DashboardPeriod;
  onChange: (period: DashboardPeriod) => void;
}

/** Segmented control built on real radio inputs: keyboard and AT support for free. */
export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  const { t } = useTranslation();
  return (
    <fieldset className="flex rounded-lg border p-1" aria-label={t('dashboard:periods.label')}>
      {PERIODS.map((period) => (
        <label
          key={period}
          className={cn(
            'flex min-h-touch flex-1 cursor-pointer items-center justify-center rounded-md px-3 text-sm',
            value === period ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
          )}
        >
          <input
            type="radio"
            name="dashboard-period"
            value={period}
            checked={value === period}
            onChange={() => {
              onChange(period);
            }}
            className="sr-only"
          />
          {t(`dashboard:periods.${period}`)}
        </label>
      ))}
    </fieldset>
  );
}
