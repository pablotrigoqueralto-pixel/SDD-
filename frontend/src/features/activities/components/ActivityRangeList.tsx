import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { Input } from '@/components/ui/input';
import { useIsStaff } from '@/features/accounts';
import { useUsers } from '@/features/admin';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { CalendarEntryRead } from '../api';
import { useActivityRange } from '../queries';

/** First and last day of the current month, in the ISO shape a date input wants. */
function monthDefaults(): { from: string; to: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const iso = (date: Date) =>
    `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
      date.getDate(),
    ).padStart(2, '0')}`;
  return { from: iso(first), to: iso(last) };
}

/**
 * "¿Qué hizo Andrés del 1 al 15?" — the same calendar feed over an explicit window.
 *
 * The backend caps the range at 92 days; its refusal is shown under the fields rather
 * than swallowed, so the user learns the rule the first time they meet it.
 */
export function ActivityRangeList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isStaff = useIsStaff();
  const defaults = monthDefaults();
  const [from, setFrom] = useState(defaults.from);
  const [to, setTo] = useState(defaults.to);
  const [ownerId, setOwnerId] = useState('');
  const reps = useUsers({ role: 'sales_rep', is_active: 'true', page_size: 200 });
  const range = useActivityRange(from, to, ownerId || undefined);

  const problem = range.error ? toProblem(range.error) : null;
  const message = problem
    ? isKnownErrorCode(problem.code)
      ? t(`errors:${problem.code}`)
      : problem.detail
    : null;

  const columns: DataListColumn<CalendarEntryRead>[] = [
    { key: 'date', header: t('activities:listado.columns.date'), cell: (e) => e.occurred_on },
    { key: 'time', header: t('activities:listado.columns.time'), cell: (e) => e.occurred_time },
    {
      key: 'type',
      header: t('activities:listado.columns.type'),
      cell: (entry) => entry.activity_type.name,
    },
    {
      key: 'account',
      header: t('activities:listado.columns.account'),
      cell: (entry) => entry.account_name,
    },
    {
      key: 'status',
      header: t('activities:listado.columns.status'),
      cell: (entry) => t(`activities:status.${entry.status}`),
    },
    {
      key: 'owner',
      header: t('activities:listado.columns.owner'),
      hideOnCard: !isStaff,
      cell: (entry) => entry.owner_name,
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-sm">
          {t('activities:listado.from')}
          <Input
            type="date"
            value={from}
            className="min-h-touch"
            onChange={(event) => {
              setFrom(event.target.value);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t('activities:listado.to')}
          <Input
            type="date"
            value={to}
            className="min-h-touch"
            onChange={(event) => {
              setTo(event.target.value);
            }}
          />
        </label>
        {isStaff ? (
          <label className="flex flex-col gap-1 text-sm">
            {t('activities:listado.rep')}
            <NativeSelect
              value={ownerId}
              aria-label={t('activities:listado.rep')}
              onChange={(event) => {
                setOwnerId(event.target.value);
              }}
            >
              <option value="">{t('activities:listado.allReps')}</option>
              {reps.data?.items.map((rep) => (
                <option key={rep.id} value={rep.id}>
                  {rep.full_name}
                </option>
              ))}
            </NativeSelect>
          </label>
        ) : null}
      </div>
      {message ? (
        <p role="alert" className="text-sm font-medium text-destructive">
          {message}
        </p>
      ) : (
        <DataList
          items={range.data?.items}
          columns={columns}
          getKey={(entry) => entry.id}
          label={t('activities:listado.tab')}
          renderTitle={(entry) => `${entry.occurred_on} · ${entry.account_name}`}
          onSelect={(entry) => {
            navigate(routes.account(entry.account_id));
          }}
          isLoading={range.isPending}
          emptyTitle={t('activities:listado.empty')}
        />
      )}
    </div>
  );
}
