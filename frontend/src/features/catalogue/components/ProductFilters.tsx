import { useTranslation } from 'react-i18next';

import { NativeSelect } from '@/components/shared/NativeSelect';
import { useBrands } from '@/features/reference';

import { PRODUCT_KINDS, type ProductListFilters } from '../api';
import { useCanViewCost } from '../hooks';

export type FilterKey = Exclude<keyof ProductListFilters, 'page' | 'page_size' | 'sort' | 'q'>;

interface ProductFiltersProps {
  filters: ProductListFilters;
  onChange: (key: FilterKey, value: string) => void;
}

/** Brand (own first), type and — for cost viewers — retired products. */
export function ProductFilters({ filters, onChange }: ProductFiltersProps) {
  const { t } = useTranslation();
  const canViewCost = useCanViewCost();
  const brands = useBrands();
  const brandOptions = [...(brands.data ?? [])]
    .filter((brand) => brand.is_active || brand.id === filters.brand_id)
    .sort((a, b) => Number(b.is_own) - Number(a.is_own) || a.name.localeCompare(b.name));

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
      <NativeSelect
        aria-label={t('catalogue:filters.brand')}
        value={filters.brand_id ?? ''}
        onChange={(event) => {
          onChange('brand_id', event.target.value);
        }}
        className="lg:w-56"
      >
        <option value="">{t('catalogue:filters.allBrands')}</option>
        {brandOptions.map((brand) => (
          <option key={brand.id} value={brand.id}>
            {brand.name}
          </option>
        ))}
      </NativeSelect>
      <NativeSelect
        aria-label={t('catalogue:filters.kind')}
        value={filters.kind ?? ''}
        onChange={(event) => {
          onChange('kind', event.target.value);
        }}
        className="lg:w-56"
      >
        <option value="">{t('catalogue:filters.allKinds')}</option>
        {PRODUCT_KINDS.map((kind) => (
          <option key={kind} value={kind}>
            {t(`catalogue:kind.${kind}`)}
          </option>
        ))}
      </NativeSelect>
      {canViewCost ? (
        <label className="flex min-h-touch items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-5 accent-primary"
            checked={filters.is_active === 'all'}
            onChange={(event) => {
              onChange('is_active', event.target.checked ? 'all' : '');
            }}
          />
          <span>{t('catalogue:filters.showInactive')}</span>
        </label>
      ) : null}
    </div>
  );
}
