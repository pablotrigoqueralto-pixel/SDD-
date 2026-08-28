import { Plus, SlidersHorizontal } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useIsStaff } from '@/features/accounts';
import { formatWhen } from '@/features/activities';
import { useUsers } from '@/features/admin';
import { useSessionStore } from '@/features/auth';
import { useDivisions, usePipelines } from '@/features/reference';
import { useIsDesktop } from '@/hooks/useMediaQuery';

import type { OpportunityListFilters, OpportunitySummaryRead } from '../api';
import { AmountText } from '../components/AmountText';
import { Board } from '../components/Board';
import { StageBadge } from '../components/StageBadge';
import { useBoard, useOpportunities } from '../queries';

const SEARCH_DEBOUNCE_MS = 300;
const STATUSES = ['open', 'won', 'lost'] as const;

function filtersFromParams(params: URLSearchParams): OpportunityListFilters {
  const filters: OpportunityListFilters = {};
  const status = params.get('status');
  if (status === 'won' || status === 'lost' || status === 'all') filters.status = status;
  for (const key of ['pipeline_id', 'stage_id', 'division_id', 'owner_id', 'account_id', 'q'] as const) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  if (params.get('is_tender') === 'true') filters.is_tender = true;
  if (params.get('is_at_risk') === 'true') filters.is_at_risk = true;
  return filters;
}

export function PipelinePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isDesktop = useIsDesktop();
  const isStaff = useIsStaff();
  const user = useSessionStore((state) => state.user);
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const [search, setSearch] = useState(filters.q ?? '');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const divisions = useDivisions();
  const pipelines = usePipelines();
  const reps = useUsers(
    isStaff ? { role: 'sales_rep', is_active: 'true', page_size: 200 } : { page_size: 1 },
  );

  const userDivisions = user?.division_ids ?? [];
  const defaultPipeline =
    pipelines.data?.find((pipeline) =>
      pipeline.division_ids.some((id) => userDivisions.includes(id)),
    ) ?? pipelines.data?.[0];
  const pipelineId = filters.pipeline_id ?? defaultPipeline?.id;

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

  const list = useOpportunities(filters);
  const boardQuery = useBoard(
    isDesktop && pipelineId
      ? {
          pipeline_id: pipelineId,
          ...(filters.division_id ? { division_id: filters.division_id } : {}),
          ...(filters.owner_id ? { owner_id: filters.owner_id } : {}),
        }
      : null,
  );

  const open = (opportunity: OpportunitySummaryRead) => {
    navigate(routes.opportunity(opportunity.id));
  };

  const columns: DataListColumn<OpportunitySummaryRead>[] = [
    { key: 'name', header: t('opportunities:opportunity'), cell: (item) => item.name },
    { key: 'account', header: t('opportunities:list.account'), cell: (item) => item.account_name },
    {
      key: 'stage',
      header: t('opportunities:list.stage'),
      cell: (item) => <StageBadge opportunity={item} />,
    },
    {
      key: 'amount',
      header: t('opportunities:list.amount'),
      cell: (item) => <AmountText amount={item.amount} />,
    },
    {
      key: 'days',
      header: t('opportunities:list.stage'),
      hideOnCard: false,
      cell: (item) => t('opportunities:list.daysInStage', { count: item.days_in_stage }),
    },
    {
      key: 'close',
      header: t('opportunities:list.closeDate'),
      cell: (item) => formatWhen(item.expected_close_date, 'date'),
    },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.opportunityNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('opportunities:new')}
    </Button>
  );

  const filterControls = (
    <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
      <NativeSelect
        aria-label={t('opportunities:filters.pipeline')}
        value={pipelineId ?? ''}
        onChange={(event) => {
          setParam('pipeline_id', event.target.value);
        }}
        className="lg:w-56"
      >
        {pipelines.data?.map((pipeline) => (
          <option key={pipeline.id} value={pipeline.id}>
            {pipeline.name_es}
          </option>
        ))}
      </NativeSelect>
      <NativeSelect
        aria-label={t('opportunities:filters.division')}
        value={filters.division_id ?? ''}
        onChange={(event) => {
          setParam('division_id', event.target.value);
        }}
        className="lg:w-56"
      >
        <option value="">{t('opportunities:filters.allDivisions')}</option>
        {divisions.data?.map((division) => (
          <option key={division.id} value={division.id}>
            {division.name_es}
          </option>
        ))}
      </NativeSelect>
      {isStaff ? (
        <NativeSelect
          aria-label={t('opportunities:filters.owner')}
          value={filters.owner_id ?? ''}
          onChange={(event) => {
            setParam('owner_id', event.target.value);
          }}
          className="lg:w-56"
        >
          <option value="">{t('opportunities:filters.allOwners')}</option>
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
          className="size-5 accent-primary"
          checked={Boolean(filters.is_tender)}
          onChange={(event) => {
            setParam('is_tender', event.target.checked ? 'true' : '');
          }}
        />
        <span>{t('opportunities:filters.tender')}</span>
      </label>
      <label className="flex min-h-touch items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-5 accent-primary"
          checked={Boolean(filters.is_at_risk)}
          onChange={(event) => {
            setParam('is_at_risk', event.target.checked ? 'true' : '');
          }}
        />
        <span>{t('opportunities:filters.atRisk')}</span>
      </label>
    </div>
  );

  return (
    <>
      <PageHeader title={t('opportunities:title')} action={newButton} />
      <div className="flex flex-col gap-3 py-3">
        <div className="flex gap-2">
          <Input
            type="search"
            aria-label={t('actions.search')}
            placeholder={t('opportunities:searchPlaceholder')}
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
        <div role="group" aria-label={t('activities:timeline.filterStatus')} className="flex flex-wrap gap-2">
          {STATUSES.map((status) => {
            const active = (filters.status ?? 'open') === status;
            return (
              <Button
                key={status}
                type="button"
                size="sm"
                variant={active ? 'default' : 'outline'}
                aria-pressed={active}
                onClick={() => {
                  setParam('status', status === 'open' ? '' : status);
                }}
              >
                {t(`opportunities:status.${status}`)}
              </Button>
            );
          })}
        </div>
        {isDesktop ? (
          filterControls
        ) : (
          <ResponsiveFormContainer
            open={filtersOpen}
            title={t('actions.filters')}
            onClose={() => {
              setFiltersOpen(false);
            }}
          >
            {filterControls}
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
      {isDesktop && (filters.status ?? 'open') === 'open' && boardQuery.data ? (
        <Board
          board={boardQuery.data}
          onSelect={open}
          onClose={(opportunity, kind) => {
            navigate(
              kind === 'win'
                ? `${routes.opportunity(opportunity.id)}/ganar`
                : `${routes.opportunity(opportunity.id)}/perder`,
            );
          }}
        />
      ) : (
        <DataList
          items={list.data?.items}
          columns={columns}
          getKey={(item) => item.id}
          renderTitle={(item) => (
            <span className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0 flex-1 truncate">{item.name}</span>
              <AmountText amount={item.amount} className="tabular-nums font-semibold" />
            </span>
          )}
          onSelect={open}
          isLoading={list.isPending}
          error={list.error}
          onRetry={() => void list.refetch()}
          emptyTitle={t('opportunities:empty')}
          emptyAction={newButton}
        />
      )}
      <Outlet />
    </>
  );
}
