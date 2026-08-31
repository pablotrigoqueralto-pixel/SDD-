import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { NativeSelect } from '@/components/shared/NativeSelect';
import { Button } from '@/components/ui/button';
import { useAccounts } from '@/features/accounts';
import { useJobTitles, useSpecialties } from '@/features/reference';

import type { ContactListFilters } from '../api';

export interface Chip {
  key: 'specialty_id' | 'account_id' | 'job_title_id' | 'is_head_of_department';
  value: string;
  label: string;
}

interface ContactFiltersProps {
  filters: ContactListFilters;
  onAdd: (key: Chip['key'], value: string) => void;
  onRemove: (chip: Chip) => void;
}

/**
 * Cumulative filters: every pick becomes a chip. Repeating a filter widens the list
 * (OR), adding a different one narrows it (AND) — the same rule the API applies.
 */
export function ContactFilters({ filters, onAdd, onRemove }: ContactFiltersProps) {
  const { t } = useTranslation();
  const specialties = useSpecialties();
  const jobTitles = useJobTitles();
  // The centre picker lists the first page of centres by name (API cap: 100).
  const accounts = useAccounts({ page: 1, page_size: 100 });
  const chosenSpecialties = filters.specialty_id ?? [];
  const chosenAccounts = filters.account_id ?? [];

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          {t('contacts:filters.specialty')}
          <NativeSelect
            value=""
            aria-label={t('contacts:filters.specialty')}
            onChange={(event) => {
              if (event.target.value) onAdd('specialty_id', event.target.value);
            }}
          >
            <option value="">{t('contacts:filters.addSpecialty')}</option>
            {specialties.data
              ?.filter((specialty) => !chosenSpecialties.includes(specialty.id))
              .map((specialty) => (
                <option key={specialty.id} value={specialty.id}>
                  {specialty.name_es}
                </option>
              ))}
          </NativeSelect>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t('contacts:filters.account')}
          <NativeSelect
            value=""
            aria-label={t('contacts:filters.account')}
            onChange={(event) => {
              if (event.target.value) onAdd('account_id', event.target.value);
            }}
          >
            <option value="">{t('contacts:filters.addAccount')}</option>
            {accounts.data?.items
              .filter((account) => !chosenAccounts.includes(account.id))
              .map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
          </NativeSelect>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t('contacts:filters.jobTitle')}
          <NativeSelect
            value={filters.job_title_id ?? ''}
            aria-label={t('contacts:filters.jobTitle')}
            onChange={(event) => {
              if (event.target.value) onAdd('job_title_id', event.target.value);
              else if (filters.job_title_id) {
                onRemove({
                  key: 'job_title_id',
                  value: filters.job_title_id,
                  label: t('contacts:filters.jobTitle'),
                });
              }
            }}
          >
            <option value="">{t('contacts:filters.anyJobTitle')}</option>
            {jobTitles.data
              ?.filter((title) => title.is_active)
              .map((title) => (
                <option key={title.id} value={title.id}>
                  {title.name_es}
                </option>
              ))}
          </NativeSelect>
        </label>
        <label className="flex items-center gap-2 self-end text-sm">
          <input
            type="checkbox"
            className="size-4"
            checked={filters.is_head_of_department === true}
            onChange={(event) => {
              if (event.target.checked) onAdd('is_head_of_department', 'true');
              else {
                onRemove({
                  key: 'is_head_of_department',
                  value: 'true',
                  label: t('contacts:filters.headOfDepartment'),
                });
              }
            }}
          />
          {t('contacts:filters.headOfDepartment')}
        </label>
      </div>
    </div>
  );
}

interface ContactFilterChipsProps {
  chips: Chip[];
  onRemove: (chip: Chip) => void;
  onClear: () => void;
}

/** Always on the page, also on mobile where the controls live inside a sheet. */
export function ContactFilterChips({ chips, onRemove, onClear }: ContactFilterChipsProps) {
  const { t } = useTranslation();
  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ul className="flex flex-wrap gap-2" aria-label={t('actions.filters')}>
        {chips.map((chip) => (
          <li key={`${chip.key}:${chip.value}`}>
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-sm">
              {chip.label}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-5"
                aria-label={t('contacts:filters.remove', { label: chip.label })}
                onClick={() => {
                  onRemove(chip);
                }}
              >
                <X className="size-3" aria-hidden="true" />
              </Button>
            </span>
          </li>
        ))}
      </ul>
      {chips.length > 1 ? (
        <Button type="button" variant="ghost" size="sm" className="h-7" onClick={onClear}>
          {t('contacts:list.clearFilters')}
        </Button>
      ) : null}
    </div>
  );
}
