import { useTranslation } from 'react-i18next';

import { NativeSelect } from '@/components/shared/NativeSelect';
import { useTerritories, useUsers } from '@/features/admin';
import { useAccountTypes, useDivisions } from '@/features/reference';

import type { AccountListFilters } from '../api';
import { useIsStaff } from '../hooks';

export type FilterKey = Exclude<keyof AccountListFilters, 'page' | 'page_size' | 'sort'>;

interface AccountFiltersProps {
  filters: AccountListFilters;
  onChange: (key: FilterKey, value: string) => void;
}

/** Filter controls shared by the inline (desktop) and sheet (mobile) layouts. */
export function AccountFilters({ filters, onChange }: AccountFiltersProps) {
  const { t } = useTranslation();
  const isStaff = useIsStaff();
  const accountTypes = useAccountTypes();
  const divisions = useDivisions();
  const territories = useTerritories({ is_active: 'true' });
  const reps = useUsers({ role: 'sales_rep', is_active: 'true' });
  const inactiveShown = filters.is_active === null;

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
      <NativeSelect
        aria-label={t('accounts:filters.type')}
        value={filters.account_type_id ?? ''}
        onChange={(event) => {
          onChange('account_type_id', event.target.value);
        }}
        className="lg:w-56"
      >
        <option value="">{t('accounts:filters.allTypes')}</option>
        {accountTypes.data?.map((type) => (
          <option key={type.id} value={type.id}>
            {type.name_es}
          </option>
        ))}
      </NativeSelect>
      <NativeSelect
        aria-label={t('accounts:filters.division')}
        value={filters.division_id ?? ''}
        onChange={(event) => {
          onChange('division_id', event.target.value);
        }}
        className="lg:w-56"
      >
        <option value="">{t('accounts:filters.allDivisions')}</option>
        {divisions.data?.map((division) => (
          <option key={division.id} value={division.id}>
            {division.name_es}
          </option>
        ))}
      </NativeSelect>
      {isStaff ? (
        <>
          <NativeSelect
            aria-label={t('accounts:filters.territory')}
            value={filters.territory_id ?? ''}
            onChange={(event) => {
              onChange('territory_id', event.target.value);
            }}
            className="lg:w-56"
          >
            <option value="">{t('accounts:filters.allTerritories')}</option>
            {territories.data?.items.map((territory) => (
              <option key={territory.id} value={territory.id}>
                {territory.name}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label={t('accounts:filters.owner')}
            value={filters.owner_id ?? ''}
            onChange={(event) => {
              onChange('owner_id', event.target.value);
            }}
            className="lg:w-56"
          >
            <option value="">{t('accounts:filters.allOwners')}</option>
            {reps.data?.items.map((rep) => (
              <option key={rep.id} value={rep.id}>
                {rep.full_name}
              </option>
            ))}
          </NativeSelect>
        </>
      ) : null}
      <label className="flex min-h-touch items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-5 accent-primary"
          checked={Boolean(filters.unassigned)}
          onChange={(event) => {
            onChange('unassigned', event.target.checked ? 'true' : '');
          }}
        />
        <span>{t('accounts:filters.unassigned')}</span>
      </label>
      <label className="flex min-h-touch items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-5 accent-primary"
          checked={inactiveShown}
          onChange={(event) => {
            onChange('is_active', event.target.checked ? 'all' : '');
          }}
        />
        <span>{t('accounts:filters.showInactive')}</span>
      </label>
    </div>
  );
}
