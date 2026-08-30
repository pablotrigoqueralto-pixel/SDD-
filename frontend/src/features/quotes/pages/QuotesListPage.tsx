import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PageHeader } from '@/components/shared/PageHeader';
import { Input } from '@/components/ui/input';
import { useUsers } from '@/features/admin';
import { formatPrice } from '@/features/catalogue';

import type { QuoteListFilters, QuoteStatus, QuoteSummaryRead } from '../api';
import { QuoteStatusBadge } from '../components/QuoteStatusBadge';
import { useSeesQuoteCost as useIsStaff } from '../hooks';
import { useQuotes } from '../queries';

const SEARCH_DEBOUNCE_MS = 300;
const STATUSES: QuoteStatus[] = ['draft', 'sent', 'accepted', 'rejected'];

function filtersFromParams(params: URLSearchParams): QuoteListFilters {
  const filters: QuoteListFilters = { status: 'all' };
  const status = params.get('status');
  if (status && (STATUSES as string[]).includes(status)) filters.status = status as QuoteStatus;
  for (const key of ['owner_id', 'account_id', 'opportunity_id', 'q'] as const) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  if (params.get('expiring') === 'true') filters.expiring = true;
  return filters;
}

/** Current versions with estado, validity and totals; rows open the quote sheet. */
export function QuotesListPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const isStaff = useIsStaff();
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const [search, setSearch] = useState(filters.q ?? '');
  const reps = useUsers(
    isStaff ? { role: 'sales_rep', is_active: 'true', page_size: 200 } : { page_size: 1 },
  );

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if ((filters.q ?? '') !== search) setParam('q', search);
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the typed text triggers
  }, [search]);

  const list = useQuotes(filters);
  const dateFormatter = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium' });

  const columns: DataListColumn<QuoteSummaryRead>[] = [
    { key: 'number', header: t('quotes:list.number'), cell: (item) => item.display_number },
    { key: 'account', header: t('quotes:list.account'), cell: (item) => item.account_name },
    {
      key: 'opportunity',
      header: t('quotes:list.opportunity'),
      cell: (item) => item.opportunity_name,
      hideOnCard: true,
    },
    {
      key: 'status',
      header: t('quotes:list.status'),
      cell: (item) => <QuoteStatusBadge quote={item} />,
    },
    {
      key: 'total',
      header: t('quotes:list.total'),
      cell: (item) => <span className="tabular-nums">{formatPrice(item.total)}</span>,
    },
    {
      key: 'validity',
      header: t('quotes:list.validity'),
      cell: (item) =>
        item.valid_until ? dateFormatter.format(new Date(`${item.valid_until}T00:00:00`)) : '—',
    },
    {
      key: 'owner',
      header: t('quotes:list.owner'),
      cell: (item) => item.owner_name,
      hideOnCard: true,
    },
  ];

  return (
    <>
      <PageHeader title={t('quotes:title')} />
      <section className="flex flex-col gap-4 py-4">
        <div className="flex flex-wrap items-end gap-3">
          <Input
            type="search"
            className="min-h-touch max-w-xs"
            placeholder={t('quotes:searchPlaceholder')}
            aria-label={t('quotes:searchPlaceholder')}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
            }}
          />
          <NativeSelect
            aria-label={t('quotes:filters.status')}
            className="max-w-40"
            value={
              typeof filters.status === 'string' && filters.status !== 'all' ? filters.status : ''
            }
            onChange={(event) => {
              setParam('status', event.target.value);
            }}
          >
            <option value="">{t('quotes:filters.allStatuses')}</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`quotes:status.${status}`)}
              </option>
            ))}
          </NativeSelect>
          {isStaff ? (
            <NativeSelect
              aria-label={t('quotes:filters.owner')}
              className="max-w-48"
              value={filters.owner_id ?? ''}
              onChange={(event) => {
                setParam('owner_id', event.target.value);
              }}
            >
              <option value="">{t('quotes:filters.allOwners')}</option>
              {reps.data?.items.map((rep) => (
                <option key={rep.id} value={rep.id}>
                  {rep.full_name}
                </option>
              ))}
            </NativeSelect>
          ) : null}
          <label className="flex min-h-touch items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4"
              checked={filters.expiring === true}
              onChange={(event) => {
                setParam('expiring', event.target.checked ? 'true' : '');
              }}
            />
            {t('quotes:filters.expiring')}
          </label>
        </div>
        <DataList
          items={list.data?.items}
          columns={columns}
          getKey={(item) => item.id}
          renderTitle={(item) => item.display_number}
          onSelect={(item) => {
            navigate(routes.quote(item.id));
          }}
          isLoading={list.isPending}
          error={list.isError ? list.error : undefined}
          onRetry={() => void list.refetch()}
          emptyTitle={t('quotes:empty')}
        />
      </section>
      <Outlet />
    </>
  );
}
