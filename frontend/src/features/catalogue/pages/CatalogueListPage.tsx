import { ChevronLeft, ChevronRight, Plus, SlidersHorizontal } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useDivisions } from '@/features/reference';
import { useIsDesktop } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/cn';

import {
  PRODUCT_KINDS,
  type ProductKind,
  type ProductListFilters,
  type ProductSummary,
} from '../api';
import { KindIcon } from '../components/KindIcon';
import { ProductFilters, type FilterKey } from '../components/ProductFilters';
import { useCanEditCatalogue } from '../hooks';
import { PRODUCT_PAGE_SIZE, useInfiniteProducts, useProducts } from '../queries';
import { formatPrice } from '../schemas';

const SEARCH_DEBOUNCE_MS = 300;

function filtersFromParams(params: URLSearchParams): ProductListFilters {
  const filters: ProductListFilters = {};
  const q = params.get('q');
  if (q) filters.q = q;
  for (const key of ['division_id', 'family_id', 'brand_id'] as const) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  const kind = params.get('kind');
  if (kind && (PRODUCT_KINDS as string[]).includes(kind)) {
    filters.kind = kind as ProductKind;
  }
  if (params.get('is_active') === 'all') filters.is_active = 'all';
  const sort = params.get('sort');
  if (sort) filters.sort = sort;
  return filters;
}

export function CatalogueListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isDesktop = useIsDesktop();
  const canEdit = useCanEditCatalogue();
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const page = Number(params.get('page') ?? '1');
  const [search, setSearch] = useState(filters.q ?? '');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const divisions = useDivisions();

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

  const paged = useProducts({ ...filters, page });
  const infinite = useInfiniteProducts(filters);
  const listQuery = isDesktop ? paged : infinite;
  const items: ProductSummary[] | undefined = isDesktop
    ? paged.data?.items
    : infinite.data?.pages.flatMap((result) => result.items);
  const total = isDesktop ? paged.data?.total : infinite.data?.pages[0]?.total;
  const pageCount = Math.max(1, Math.ceil((total ?? 0) / PRODUCT_PAGE_SIZE));

  const columns: DataListColumn<ProductSummary>[] = [
    { key: 'name', header: t('catalogue:form.name'), cell: (product) => product.name },
    { key: 'brand', header: t('catalogue:list.brand'), cell: (product) => product.brand.name },
    { key: 'family', header: t('catalogue:list.family'), cell: (product) => product.family.name },
    { key: 'sku', header: t('catalogue:list.sku'), cell: (product) => product.sku },
    {
      key: 'kind',
      header: t('catalogue:list.kind'),
      hideOnCard: true,
      cell: (product) => t(`catalogue:kind.${product.kind}`),
    },
    {
      key: 'price',
      header: t('catalogue:list.price'),
      cell: (product) => formatPrice(product.list_price),
    },
  ];

  const newButton = canEdit ? (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.productNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('catalogue:new')}
    </Button>
  ) : null;

  const onFilterChange = (key: FilterKey, value: string) => {
    setParam(key, value);
  };

  return (
    <>
      <PageHeader title={t('catalogue:title')} action={newButton} />
      <div className="flex flex-col gap-3 py-3">
        <div className="flex gap-2">
          <Input
            type="search"
            aria-label={t('actions.search')}
            placeholder={t('catalogue:searchPlaceholder')}
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
        <div
          role="group"
          aria-label={t('catalogue:filters.division')}
          className="flex flex-wrap gap-2"
        >
          <Button
            type="button"
            size="sm"
            variant={filters.division_id ? 'outline' : 'default'}
            aria-pressed={!filters.division_id}
            onClick={() => {
              setParam('division_id', '');
            }}
          >
            {t('catalogue:filters.allDivisions')}
          </Button>
          {divisions.data?.map((division) => (
            <Button
              key={division.id}
              type="button"
              size="sm"
              variant={filters.division_id === division.id ? 'default' : 'outline'}
              aria-pressed={filters.division_id === division.id}
              onClick={() => {
                setParam('division_id', division.id);
              }}
            >
              {division.name_es}
            </Button>
          ))}
        </div>
        {isDesktop ? (
          <ProductFilters filters={filters} onChange={onFilterChange} />
        ) : (
          <ResponsiveFormContainer
            open={filtersOpen}
            title={t('actions.filters')}
            onClose={() => {
              setFiltersOpen(false);
            }}
          >
            <ProductFilters filters={filters} onChange={onFilterChange} />
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
        getKey={(product) => product.id}
        renderTitle={(product) => (
          <span className="flex flex-wrap items-center gap-2">
            <KindIcon kind={product.kind} className="size-4 text-muted-foreground" />
            <span className={cn(!product.is_active && 'text-muted-foreground line-through')}>
              {product.name}
            </span>
            {product.is_active ? null : (
              <Badge variant="outline">{t('catalogue:list.retired')}</Badge>
            )}
          </span>
        )}
        onSelect={(product) => {
          navigate(routes.product(product.id));
        }}
        isLoading={listQuery.isPending}
        error={listQuery.error}
        onRetry={() => void listQuery.refetch()}
        emptyTitle={t('catalogue:empty')}
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
        <nav className="flex items-center justify-end gap-2 py-3" aria-label={t('catalogue:title')}>
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
