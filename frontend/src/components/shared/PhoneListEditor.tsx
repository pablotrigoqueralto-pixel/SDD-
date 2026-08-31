import { ArrowUp, Plus, X } from 'lucide-react';
import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export const phoneRowSchema = z.object({
  label: z.string().trim().max(60),
  number: z.string().trim().max(30),
  extension: z.string().trim().max(10),
  note: z.string().trim().max(200),
});

export interface PhoneInput {
  label: string;
  number: string;
  extension: string;
  note: string;
}

export const PHONE_LABEL_SUGGESTIONS = [
  'Principal',
  'Secretaría',
  'Servicio',
  'Consulta',
  'Despacho',
  'Extensión',
  'Móvil',
  'Fax',
] as const;

export function emptyPhone(): PhoneInput {
  return { label: '', number: '', extension: '', note: '' };
}

interface PhoneListEditorProps {
  value: PhoneInput[];
  onChange: (phones: PhoneInput[]) => void;
  /** Backend `phone_invalid` for one row, so the message lands on the offending phone. */
  invalidIndex?: number | undefined;
}

/** Labelled phones for accounts and contacts: order is priority, the first is primary. */
export function PhoneListEditor({ value, onChange, invalidIndex }: PhoneListEditorProps) {
  const { t } = useTranslation();
  const listId = useId();

  const update = (index: number, patch: Partial<PhoneInput>) => {
    onChange(value.map((phone, position) => (position === index ? { ...phone, ...patch } : phone)));
  };
  const remove = (index: number) => {
    onChange(value.filter((_, position) => position !== index));
  };
  const promote = (index: number) => {
    const next = [...value];
    const [row] = next.splice(index, 1);
    if (row) next.unshift(row);
    onChange(next);
  };

  return (
    <div className="flex flex-col gap-3">
      <datalist id={listId}>
        {PHONE_LABEL_SUGGESTIONS.map((label) => (
          <option key={label} value={label} />
        ))}
      </datalist>

      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('accounts:phones.empty')}</p>
      ) : null}

      <ul className="flex flex-col gap-3">
        {value.map((phone, index) => (
          <li key={index} className="flex flex-col gap-2 rounded-lg border p-3">
            <div className="flex flex-col gap-2 lg:flex-row">
              <label
                className="flex flex-1 flex-col gap-1 text-sm"
                htmlFor={`${listId}-label-${index}`}
              >
                {t('accounts:phones.label')}
                <Input
                  id={`${listId}-label-${index}`}
                  list={listId}
                  value={phone.label}
                  onChange={(event) => {
                    update(index, { label: event.target.value });
                  }}
                  placeholder={t('accounts:phones.labelPlaceholder')}
                />
              </label>
              <label
                className="flex flex-1 flex-col gap-1 text-sm"
                htmlFor={`${listId}-number-${index}`}
              >
                {t('accounts:phones.number')}
                <Input
                  id={`${listId}-number-${index}`}
                  type="tel"
                  value={phone.number}
                  onChange={(event) => {
                    update(index, { number: event.target.value });
                  }}
                />
              </label>
            </div>
            <div className="flex flex-col gap-2 lg:flex-row">
              <label
                className="flex w-full flex-col gap-1 text-sm lg:w-32"
                htmlFor={`${listId}-extension-${index}`}
              >
                {t('accounts:phones.extension')}
                <Input
                  id={`${listId}-extension-${index}`}
                  inputMode="numeric"
                  value={phone.extension}
                  onChange={(event) => {
                    update(index, { extension: event.target.value });
                  }}
                />
              </label>
              <label
                className="flex flex-1 flex-col gap-1 text-sm"
                htmlFor={`${listId}-note-${index}`}
              >
                {t('accounts:phones.note')}
                <Input
                  id={`${listId}-note-${index}`}
                  value={phone.note}
                  onChange={(event) => {
                    update(index, { note: event.target.value });
                  }}
                />
              </label>
            </div>
            {index === 0 ? (
              <p className="text-xs text-muted-foreground">{t('accounts:phones.primary')}</p>
            ) : null}
            {invalidIndex === index ? (
              <p role="alert" className="text-sm text-destructive">
                {t('errors:phone_invalid')}
              </p>
            ) : null}
            <div className="flex gap-2">
              {index > 0 ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="min-h-touch"
                  onClick={() => {
                    promote(index);
                  }}
                >
                  <ArrowUp className="size-4" aria-hidden="true" />
                  {t('accounts:phones.makePrimary')}
                </Button>
              ) : null}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="min-h-touch"
                onClick={() => {
                  remove(index);
                }}
                aria-label={t('accounts:phones.removeOne', {
                  label: phone.label || t('accounts:phones.label'),
                })}
              >
                <X className="size-4" aria-hidden="true" />
                {t('actions.remove')}
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <Button
        type="button"
        variant="outline"
        size="sm"
        className="min-h-touch self-start"
        onClick={() => {
          onChange([...value, emptyPhone()]);
        }}
      >
        <Plus className="size-4" aria-hidden="true" />
        {t('accounts:phones.add')}
      </Button>
    </div>
  );
}

/** Form rows -> API payload: blanks dropped, empty optional fields omitted. */
export function toPhonePayload(
  phones: PhoneInput[],
): { label: string; number: string; extension?: string; note?: string }[] {
  return phones
    .filter((phone) => phone.label.trim() && phone.number.trim())
    .map((phone) => ({
      label: phone.label.trim(),
      number: phone.number.trim(),
      ...(phone.extension.trim() ? { extension: phone.extension.trim() } : {}),
      ...(phone.note.trim() ? { note: phone.note.trim() } : {}),
    }));
}

/** API payload -> form rows. */
export function toPhoneRows(
  phones: { label: string; number: string; extension: string | null; note: string | null }[],
): PhoneInput[] {
  return phones.map((phone) => ({
    label: phone.label,
    number: phone.number,
    extension: phone.extension ?? '',
    note: phone.note ?? '',
  }));
}
