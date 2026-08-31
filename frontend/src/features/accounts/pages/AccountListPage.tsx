import { ChevronLeft, ChevronRight, Plus, SlidersHorizontal } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { formatWhen } from '@/features/activities';
import { labelOf, useAccountTypes } from '@/features/reference';
import { useIsDesktop } from '@/hooks/useMediaQuery';

import type { AccountListFilters, AccountSummaryRead } from '../api';
import { AccountFilters, type FilterKey } from '../components/AccountFilters';
import { AccountBadges } from '../components/AccountHeader';
import { ACCOUNT_PAGE_SIZE, useAccounts, useInfiniteAccounts } from '../queries';

const SEARCH_DEBOUNCE_MS = 300;

function filtersFromParams(params: URLSearchParams): AccountListFilters {
  const filters: AccountListFilters = {};
  const q = params.get('q');
  if (q) filters.q = q;
  for (const key of ['account_type_id', 'territory_id', 'owner_id', 'division_id'] as const) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  if (params.get('unassigned') === 'true') filters.unassigned = true;
  if (params.get('is_active') === 'all') filters.is_active = null;
  const sort = params.get('sort');
  if (sort) filters.sort = sort;
  return filters;
}

export function AccountListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isDesktop = useIsDesktop();
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const page = Number(params.get('page') ?? '1');
  const [search, setSearch] = useState(filters.q ?? '');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const accountTypes = useAccountTypes();

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
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

  const paged = useAccounts({ ...filters, page });
  const infinite = useInfiniteAccounts(filters);
  const listQuery = isDesktop ? paged : infinite;
  const items: AccountSummaryRead[] | undefined = isDesktop
    ? paged.data?.items
    : infinite.data?.pages.flatMap((result) => result.items);
  const total = isDesktop ? paged.data?.total : infinite.data?.pages[0]?.total;
  const pageCount = Math.max(1, Math.ceil((total ?? 0) / ACCOUNT_PAGE_SIZE));

  const columns: DataListColumn<AccountSummaryRead>[] = [
    { key: 'name', header: t('accounts:form.name'), cell: (account) => account.name },
    {
      key: 'type',
      header: t('accounts:list.type'),
      cell: (account) =>
        labelOf(accountTypes.data, account.account_type_id, (type) => type.name_es),
    },
    { key: 'city', header: t('accounts:list.city'), cell: (account) => account.city ?? '' },
    {
      key: 'owner',
      header: t('accounts:list.owner'),
      cell: (account) => account.owner_name ?? '',
    },
    {
      key: 'contact',
      header: t('accounts:list.contact'),
      hideOnCard: true,
      cell: (account) => account.primary_contact_name ?? '',
    },
    {
      key: 'phone',
      header: t('accounts:list.phone'),
      hideOnCard: true,
      cell: (account) =>
        account.primary_phone ? (
          <a className="underline" href={`tel:${account.primary_phone}`}>
            {account.primary_phone}
          </a>
        ) : (
          ''
        ),
    },
    {
      key: 'last_contact',
      header: t('activities:recency.lastContact'),
      cell: (account) =>
        account.last_contact_at
          ? formatWhen(account.last_contact_at, 'date')
          : t('activities:recency.never'),
    },
    {
      key: 'badges',
      header: t('admin:users.filterActive'),
      hideOnCard: true,
      cell: (account) => (
        <span className="flex flex-wrap gap-1">
          <AccountBadges account={account} />
        </span>
      ),
    },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.accountNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('accounts:new')}
    </Button>
  );

  const onFilterChange = (key: FilterKey, value: string) => {
    setParam(key, value);
  };

  return (
    <>
      <PageHeader title={t('accounts:title')} action={newButton} />
      <div className="flex flex-col gap-3 py-3">
        <div className="flex gap-2">
          <Input
            type="search"
            aria-label={t('actions.search')}
            placeholder={t('accounts:searchPlaceholder')}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
            }}
            className="min-h-touch lg:max-w-sm"
          />
          {isDesktop ? null : (
            <Button
              variant="outline"
              className="min-h-touch"
              onClick={() => {
                setFiltersOpen(true);
              }}
            >
              <SlidersHorizontal className="size-4" aria-hidden="true" />
              {t('actions.filters')}
            </Button>
          )}
        </div>
        {isDesktop ? (
          <AccountFilters filters={filters} onChange={onFilterChange} />
        ) : (
          <ResponsiveFormContainer
            open={filtersOpen}
            title={t('actions.filters')}
            onClose={() => {
              setFiltersOpen(false);
            }}
          >
            <AccountFilters filters={filters} onChange={onFilterChange} />
            <Button
              className="mt-4 min-h-touch w-full"
              onClick={() => {
                setFiltersOpen(false);
              }}
            >
              {t('actions.apply')}
            </Button>
          </ResponsiveFormContainer>
        )}
      </div>
      <DataList
        items={items}
        columns={columns}
        getKey={(account) => account.id}
        renderTitle={(account) => (
          <span className="flex flex-wrap items-center gap-2">
            {account.name}
            <AccountBadges account={account} />
          </span>
        )}
        onSelect={(account) => {
          navigate(routes.account(account.id));
        }}
        isLoading={listQuery.isPending}
        error={listQuery.error}
        onRetry={() => void listQuery.refetch()}
        emptyTitle={t('accounts:empty')}
        emptyAction={newButton}
      />
      {!isDesktop && infinite.hasNextPage ? (
        <div className="py-3">
          <Button
            variant="outline"
            className="min-h-touch w-full"
            disabled={infinite.isFetchingNextPage}
            onClick={() => void infinite.fetchNextPage()}
          >
            {t('actions.loadMore')}
          </Button>
        </div>
      ) : null}
      {isDesktop && pageCount > 1 ? (
        <nav className="flex items-center justify-end gap-2 py-3" aria-label={t('accounts:title')}>
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
          <span className="text-sm text-muted-foreground">
            {page}
            {' / '}
            {pageCount}
          </span>
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
