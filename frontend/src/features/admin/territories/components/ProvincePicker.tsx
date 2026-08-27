import { useTranslation } from 'react-i18next';

import { CheckboxList } from '@/components/shared/CheckboxList';
import { provincesByCommunity } from '@/lib/provinces';

import type { TerritoryRead } from '../../types';

interface ProvincePickerProps {
  value: string[];
  onChange: (value: string[]) => void;
  /** Existing territories, to disable provinces owned by another one. */
  territories: TerritoryRead[];
  currentTerritoryId?: string | undefined;
  /** Province/owner reported by the backend after a failed save (race with another admin). */
  conflict?: { code: string; owner: string } | null;
}

export function ProvincePicker({
  value,
  onChange,
  territories,
  currentTerritoryId,
  conflict,
}: ProvincePickerProps) {
  const { t } = useTranslation();
  const ownerByProvince = new Map<string, string>();
  for (const territory of territories) {
    if (territory.id === currentTerritoryId) continue;
    for (const code of territory.provinces) ownerByProvince.set(code, territory.name);
  }

  return (
    <div className="flex max-h-72 flex-col gap-3 overflow-y-auto rounded-md border p-2">
      {provincesByCommunity().map((group) => (
        <fieldset key={group.community}>
          <legend className="px-2 text-xs font-semibold uppercase text-muted-foreground">
            {group.community}
          </legend>
          <CheckboxList
            name="provinces"
            value={value}
            onChange={onChange}
            options={group.provinces.map((province) => {
              const owner =
                ownerByProvince.get(province.code) ??
                (conflict?.code === province.code ? conflict.owner : undefined);
              return {
                value: province.code,
                label: province.name,
                disabled: Boolean(owner),
                hint: owner
                  ? t('admin:territories.form.provinceTaken', { territory: owner })
                  : undefined,
              };
            })}
          />
        </fieldset>
      ))}
    </div>
  );
}
