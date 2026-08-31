import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { formatPrice } from '@/features/catalogue';

import type { BreakdownRowRead, StageRowRead } from '../api';

function barWidth(amount: string, max: number): string {
  if (max <= 0) return '0%';
  return `${String(Math.max(4, Math.round((Number(amount) / max) * 100)))}%`;
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2 rounded-lg border p-4">
      <h2 className="text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function SectionEmpty() {
  const { t } = useTranslation();
  return <p className="text-sm text-muted-foreground">{t('dashboard:empty')}</p>;
}

function Bar({ width }: { width: string }) {
  return (
    <div className="h-2 w-full rounded-full bg-muted" aria-hidden="true">
      <div className="h-2 rounded-full bg-primary" style={{ width }} />
    </div>
  );
}

export function StageSection({ rows }: { rows: StageRowRead[] }) {
  const { t } = useTranslation();
  const max = Math.max(0, ...rows.map((row) => Number(row.amount)));
  return (
    <Section title={t('dashboard:sections.stages')}>
      {rows.length === 0 ? (
        <SectionEmpty />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((row) => (
            <li key={row.stage_id} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{row.name}</span>
                <span className="text-muted-foreground">
                  {formatPrice(row.amount)} · {t('dashboard:stageCount', { count: row.count })}
                </span>
              </div>
              <Bar width={barWidth(row.amount, max)} />
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function BreakdownSection({ title, rows }: { title: string; rows: BreakdownRowRead[] }) {
  const { t } = useTranslation();
  const max = Math.max(0, ...rows.map((row) => Number(row.won_amount)));
  return (
    <Section title={title}>
      {rows.length === 0 ? (
        <SectionEmpty />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{row.name}</span>
                <span className="tabular-nums">{formatPrice(row.won_amount)}</span>
              </div>
              <Bar width={barWidth(row.won_amount, max)} />
              <p className="text-xs text-muted-foreground">
                {t('dashboard:breakdown.forecast')} {formatPrice(row.forecast_amount)} ·{' '}
                {t('dashboard:breakdown.open')} {formatPrice(row.open_amount)}
                {row.conversion_rate === null
                  ? ''
                  : ` · ${t('dashboard:breakdown.conversion')} ${String(
                      Math.round(row.conversion_rate * 100),
                    )} %`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
