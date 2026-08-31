import { useTranslation } from 'react-i18next';

import { formatPrice } from '@/features/catalogue';

import type { SummaryRead } from '../api';

function formatRate(rate: number | null | undefined): string | null {
  if (rate === null || rate === undefined) return null;
  return `${String(Math.round(rate * 100))} %`;
}

interface CardProps {
  label: string;
  value: string;
  detail?: string | undefined;
  hint?: string | undefined;
}

function KpiCard({ label, value, detail, hint }: CardProps) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      {detail ? <p className="text-sm text-muted-foreground">{detail}</p> : null}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function KpiCards({ summary }: { summary: SummaryRead }) {
  const { t } = useTranslation();
  const { won, conversion, forecast, open_pipeline: openPipeline } = summary;
  const rate = formatRate(conversion.rate);
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <KpiCard
        label={t('dashboard:kpis.won')}
        value={formatPrice(won.amount)}
        detail={`${t('dashboard:kpis.wonCount', { count: won.count })} · ${t(
          'dashboard:kpis.previous',
          { value: formatPrice(won.previous_amount) },
        )}`}
      />
      <KpiCard
        label={t('dashboard:kpis.conversion')}
        value={rate ?? t('dashboard:kpis.noRate')}
        detail={
          conversion.closed > 0
            ? `${t('dashboard:kpis.closedCounts', {
                won: conversion.won,
                closed: conversion.closed,
              })}${
                formatRate(conversion.previous_rate)
                  ? ` · ${t('dashboard:kpis.previous', {
                      value: formatRate(conversion.previous_rate) ?? '',
                    })}`
                  : ''
              }`
            : undefined
        }
      />
      <KpiCard
        label={t('dashboard:kpis.forecast')}
        value={formatPrice(forecast.amount)}
        detail={t('dashboard:kpis.forecastCount', { count: forecast.count })}
        hint={t('dashboard:kpis.forecastHint')}
      />
      <KpiCard
        label={t('dashboard:kpis.openPipeline')}
        value={formatPrice(openPipeline.amount)}
        detail={t('dashboard:kpis.openCount', { count: openPipeline.count })}
      />
    </div>
  );
}
