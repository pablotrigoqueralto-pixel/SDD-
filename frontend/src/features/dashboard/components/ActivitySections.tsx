import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/badge';

import type { ActivityRowRead, NeglectedAccountsRead } from '../api';
import { Section, SectionEmpty } from './BarSections';

export function ActivitySection({ rows }: { rows: ActivityRowRead[] }) {
  const { t } = useTranslation();
  return (
    <Section title={t('dashboard:sections.activity')}>
      {rows.length === 0 ? (
        <SectionEmpty />
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((row) => (
            <li
              key={row.user_id}
              className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border p-3 text-sm"
            >
              <span className="font-medium">{row.name}</span>
              <span className="text-muted-foreground">
                {t('dashboard:activityTotal', { count: row.total })}
                {row.by_type.length > 0
                  ? ` · ${row.by_type
                      .map((item) => `${item.name} ${String(item.count)}`)
                      .join(' · ')}`
                  : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function NeglectedSection({ data }: { data: NeglectedAccountsRead }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <section
      aria-label={t('dashboard:sections.neglected')}
      className="flex flex-col gap-2 rounded-lg border p-4"
    >
      <h2 className="flex items-center justify-between text-base font-semibold">
        {t('dashboard:sections.neglected')}
        {data.total > 0 ? <Badge variant="secondary">{data.total}</Badge> : null}
      </h2>
      {data.items.length === 0 ? (
        <SectionEmpty />
      ) : (
        <ul className="flex flex-col gap-2">
          {data.items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => {
                  navigate(routes.account(item.id));
                }}
                className="flex min-h-touch w-full items-center justify-between gap-2 rounded-lg border p-3 text-left text-sm hover:bg-muted"
              >
                <span className="truncate font-medium">{item.name}</span>
                <span className="shrink-0 text-muted-foreground">
                  {item.days_since_contact === null
                    ? t('dashboard:neglected.never')
                    : t('dashboard:neglected.days', { count: item.days_since_contact })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
