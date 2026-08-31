import { ChevronLeft, ChevronRight, SlidersHorizontal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAccounts } from '@/features/accounts';
import { labelOf, useJobTitles, useSpecialties } from '@/features/reference';
import { useIsDesktop } from '@/hooks/useMediaQuery';

import type { ContactListFilters, ContactSummaryRead } from '../api';
import { ContactFilterChips, ContactFilters, type Chip } from '../components/ContactFilters';
import { CONTACT_PAGE_SIZE, useContacts, useInfiniteContacts } from '../queries';

const SEARCH_DEBOUNCE_MS = 300;

const fullName = (contact: ContactSummaryRead) => `${contact.first_name} ${contact.last_name}`;

/** The whole filter state lives in the URL, so a filtered list can be shared or reopened. */
function filtersFromParams(params: URLSearchParams): ContactListFilters {
  const filters: ContactListFilters = {};
  const q = params.get('q');
  if (q) filters.q = q;
  const specialtyIds = params.getAll('specialty_id');
  if (specialtyIds.length > 0) filters.specialty_id = specialtyIds;
  const accountIds = params.getAll('account_id');
  if (accountIds.length > 0) filters.account_id = accountIds;
  const jobTitleId = params.get('job_title_id');
  if (jobTitleId) filters.job_title_id = jobTitleId;
  if (params.get('is_head_of_department') === 'true') filters.is_head_of_department = true;
  return filters;
}

export function ContactListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isDesktop = useIsDesktop();
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const page = Number(params.get('page') ?? '1');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(filters.q ?? '');
  // react-router's setSearchParams closes over the params of the render that created it,
  // so the debounced search below would write back a snapshot taken before the user picked
  // a filter — dropping it. Every mutation reads this ref instead.
  const paramsRef = useRef(params);
  paramsRef.current = params;
  const specialties = useSpecialties();
  const jobTitles = useJobTitles();
  const accounts = useAccounts({ page: 1, page_size: 100 });

  const mutateParams = (mutate: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(paramsRef.current);
    mutate(next);
    paramsRef.current = next;
    setParams(next, { replace: true });
  };

  const setParam = (key: string, value: string) => {
    mutateParams((next) => {
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== 'page') next.delete('page'); // a narrower list starts at its first page
    });
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

  const specialtyName = (id: string | null) =>
    labelOf(specialties.data, id, (specialty) => specialty.name_es);

  const chips: Chip[] = [
    ...(filters.specialty_id ?? []).map((id) => ({
      key: 'specialty_id' as const,
      value: id,
      label: specialtyName(id),
    })),
    ...(filters.account_id ?? []).map((id) => ({
      key: 'account_id' as const,
      value: id,
      label: labelOf(accounts.data?.items, id, (account) => account.name),
    })),
    ...(filters.job_title_id
      ? [
          {
            key: 'job_title_id' as const,
            value: filters.job_title_id,
            label: labelOf(jobTitles.data, filters.job_title_id, (title) => title.name_es),
          },
        ]
      : []),
    ...(filters.is_head_of_department
      ? [
          {
            key: 'is_head_of_department' as const,
            value: 'true',
            label: t('contacts:filters.headOfDepartment'),
          },
        ]
      : []),
  ];

  const addFilter = (key: Chip['key'], value: string) => {
    mutateParams((next) => {
      if (key === 'is_head_of_department' || key === 'job_title_id') next.set(key, value);
      else if (!next.getAll(key).includes(value)) next.append(key, value);
      next.delete('page');
    });
  };

  const removeFilter = (chip: Chip) => {
    mutateParams((next) => {
      const remaining = next.getAll(chip.key).filter((value) => value !== chip.value);
      next.delete(chip.key);
      for (const value of remaining) next.append(chip.key, value);
      next.delete('page');
    });
  };

  const clearFilters = () => {
    setSearch('');
    paramsRef.current = new URLSearchParams();
    setParams(paramsRef.current, { replace: true });
  };

  const paged = useContacts({ ...filters, page });
  const infinite = useInfiniteContacts(filters);
  const listQuery = isDesktop ? paged : infinite;
  const items: ContactSummaryRead[] | undefined = isDesktop
    ? paged.data?.items
    : infinite.data?.pages.flatMap((result) => result.items);
  const total = isDesktop ? paged.data?.total : infinite.data?.pages[0]?.total;
  const pageCount = Math.max(1, Math.ceil((total ?? 0) / CONTACT_PAGE_SIZE));

  const columns: DataListColumn<ContactSummaryRead>[] = [
    {
      key: 'name',
      header: t('contacts:form.lastName'),
      cell: (contact) => fullName(contact),
    },
    {
      key: 'specialty',
      header: t('contacts:form.speciality'),
      cell: (contact) => specialtyName(contact.specialty_id),
    },
    {
      key: 'job_title',
      header: t('contacts:form.jobTitle'),
      cell: (contact) => labelOf(jobTitles.data, contact.job_title_id, (title) => title.name_es),
    },
    {
      key: 'account',
      header: t('accounts:title'),
      cell: (contact) => contact.account_name,
    },
    {
      key: 'phone',
      header: t('contacts:form.phones'),
      hideOnCard: true,
      cell: (contact) =>
        contact.primary_phone ? (
          <a className="underline" href={`tel:${contact.primary_phone}`}>
            {contact.primary_phone}
          </a>
        ) : (
          ''
        ),
    },
  ];

  return (
    <>
      <PageHeader title={t('contacts:list.title')} />
      <div className="flex flex-col gap-3 py-3">
        <Input
          type="search"
          aria-label={t('contacts:list.search')}
          placeholder={t('contacts:list.search')}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
          }}
          className="min-h-touch lg:max-w-sm"
        />
        {isDesktop ? (
          <ContactFilters filters={filters} onAdd={addFilter} onRemove={removeFilter} />
        ) : (
          <>
            <Button
              variant="outline"
              className="min-h-touch self-start"
              onClick={() => {
                setFiltersOpen(true);
              }}
            >
              <SlidersHorizontal className="size-4" aria-hidden="true" />
              {t('actions.filters')}
            </Button>
            <ResponsiveFormContainer
              open={filtersOpen}
              title={t('actions.filters')}
              onClose={() => {
                setFiltersOpen(false);
              }}
            >
              <ContactFilters filters={filters} onAdd={addFilter} onRemove={removeFilter} />
              <Button
                className="mt-4 min-h-touch w-full"
                onClick={() => {
                  setFiltersOpen(false);
                }}
              >
                {t('actions.apply')}
              </Button>
            </ResponsiveFormContainer>
          </>
        )}
        <ContactFilterChips chips={chips} onRemove={removeFilter} onClear={clearFilters} />
      </div>
      <DataList
        items={items}
        columns={columns}
        getKey={(contact) => contact.id}
        label={t('contacts:list.title')}
        renderTitle={(contact) => (
          <span className="flex flex-wrap items-center gap-2">
            <span>{fullName(contact)}</span>
            {contact.is_head_of_department ? (
              <Badge variant="secondary">{t('contacts:card.headOfDepartment')}</Badge>
            ) : null}
          </span>
        )}
        onSelect={(contact) => {
          navigate(routes.account(contact.account_id));
        }}
        isLoading={listQuery.isPending}
        error={listQuery.error}
        onRetry={() => void listQuery.refetch()}
        emptyTitle={t('contacts:list.empty')}
        emptyAction={
          <Button variant="outline" className="min-h-touch" onClick={clearFilters}>
            {t('contacts:list.clearFilters')}
          </Button>
        }
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
        <nav
          className="flex items-center justify-end gap-2 py-3"
          aria-label={t('contacts:list.title')}
        >
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
    </>
  );
}
