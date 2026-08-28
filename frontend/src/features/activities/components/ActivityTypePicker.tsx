import { useTranslation } from 'react-i18next';

import { useActivityTypes } from '@/features/reference';
import { cn } from '@/lib/cn';

import { ActivityTypeIcon } from './ActivityTypeIcon';

interface ActivityTypePickerProps {
  name: string;
  value: string;
  onChange: (typeId: string) => void;
  /** Hide types that cannot be planned (Nota) when planning. */
  excludeNotes?: boolean;
  compact?: boolean;
}

/** Segmented radio group with the master icons: one tap picks Visita, Llamada, … */
export function ActivityTypePicker({
  name,
  value,
  onChange,
  excludeNotes = false,
  compact = false,
}: ActivityTypePickerProps) {
  const { t } = useTranslation();
  const types = useActivityTypes();
  const options = (types.data ?? []).filter(
    (type) => type.is_active && (!excludeNotes || type.counts_as_contact),
  );
  return (
    <fieldset>
      <legend className="text-sm font-medium">{t('activities:form.type')}</legend>
      <div
        className={cn('mt-1 grid gap-2', compact ? 'grid-cols-3' : 'grid-cols-3 sm:grid-cols-6')}
      >
        {options.map((type) => (
          <label
            key={type.id}
            className={cn(
              'flex min-h-touch cursor-pointer flex-col items-center justify-center gap-1 rounded-md border px-2 py-2 text-xs',
              value === type.id ? 'border-primary bg-accent font-semibold' : 'hover:bg-muted',
            )}
          >
            <input
              type="radio"
              name={name}
              value={type.id}
              checked={value === type.id}
              onChange={() => {
                onChange(type.id);
              }}
              className="sr-only"
            />
            <ActivityTypeIcon icon={type.icon} />
            <span>{type.name_es}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
