import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { labelOf, useDivisions } from '@/features/reference';

import type { BrandFilters, BrandRead } from '../api';
import { useBrandList } from '../queries';

export function BrandListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const filters: BrandFilters = {
    q: params.get('q') ?? '',
    is_own: (params.get('is_own') ?? '') as BrandFilters['is_own'],
  };
  const brands = useBrandList(filters);
  const divisions = useDivisions();

  const setFilter = (key: keyof BrandFilters, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const kindBadge = (brand: BrandRead) => (
    <Badge variant={brand.is_own ? 'default' : 'secondary'}>
      {brand.is_own ? t('reference:brandKind.own') : t('reference:brandKind.competitor')}
    </Badge>
  );

  const columns: DataListColumn<BrandRead>[] = [
    { key: 'name', header: t('admin:brands.form.name'), cell: (brand) => brand.name },
    { key: 'kind', header: t('admin:brands.form.kind'), cell: kindBadge },
    {
      key: 'divisions',
      header: t('admin:brands.form.divisions'),
      cell: (brand) =>
        brand.division_ids.map((id) => labelOf(divisions.data, id, (d) => d.name_es)).join(', '),
    },
    {
      key: 'status',
      header: t('admin:users.filterActive'),
      hideOnCard: true,
      cell: (brand) =>
        brand.is_active ? null : <Badge variant="outline">{t('reference:status.inactive')}</Badge>,
    },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.adminBrandNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('admin:brands.new')}
    </Button>
  );

  return (
    <>
      <PageHeader title={t('admin:brands.title')} backTo={routes.admin} action={newButton} />
      <div className="flex flex-col gap-3 py-3 lg:flex-row">
        <Input
          type="search"
          aria-label={t('actions.search')}
          placeholder={t('admin:brands.searchPlaceholder')}
          value={filters.q ?? ''}
          onChange={(event) => {
            setFilter('q', event.target.value);
          }}
          className="min-h-touch lg:max-w-xs"
        />
        <NativeSelect
          aria-label={t('admin:brands.filterKind')}
          value={filters.is_own ?? ''}
          onChange={(event) => {
            setFilter('is_own', event.target.value);
          }}
          className="lg:w-56"
        >
          <option value="">{t('admin:brands.all')}</option>
          <option value="true">{t('admin:brands.own')}</option>
          <option value="false">{t('admin:brands.competitor')}</option>
        </NativeSelect>
      </div>
      <DataList
        items={brands.data}
        columns={columns}
        getKey={(brand) => brand.id}
        renderTitle={(brand) => (
          <span className="flex items-center gap-2">
            {brand.name}
            {brand.is_active ? null : (
              <Badge variant="outline">{t('reference:status.inactive')}</Badge>
            )}
          </span>
        )}
        onSelect={(brand) => {
          navigate(routes.adminBrand(brand.id));
        }}
        isLoading={brands.isPending}
        error={brands.error}
        onRetry={() => void brands.refetch()}
        emptyTitle={t('admin:brands.empty')}
        emptyAction={newButton}
      />
      <Outlet />
    </>
  );
}
