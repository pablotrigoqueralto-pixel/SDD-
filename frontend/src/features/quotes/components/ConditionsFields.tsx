import type { Control, FieldPath, FieldValues } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';

interface ConditionsFieldsProps<T extends FieldValues> {
  control: Control<T>;
  /** Prefix of the conditions group inside the parent form (e.g. "conditions"). */
  prefix: string;
}

/** Validez, plazo, forma de pago and garantía — shared by the quote form and admin defaults. */
export function ConditionsFields<T extends FieldValues>({
  control,
  prefix,
}: ConditionsFieldsProps<T>) {
  const { t } = useTranslation();
  const name = (suffix: string) => `${prefix}.${suffix}` as FieldPath<T>;
  return (
    <fieldset className="grid gap-3 sm:grid-cols-2">
      <legend className="col-span-full text-sm font-medium">{t('quotes:conditions.title')}</legend>
      <FormField
        control={control}
        name={name('validez_dias')}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{t('quotes:conditions.validity')}</FormLabel>
            <FormControl>
              <Input className="min-h-touch" inputMode="numeric" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
      <FormField
        control={control}
        name={name('plazo_entrega')}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{t('quotes:conditions.delivery')}</FormLabel>
            <FormControl>
              <Input className="min-h-touch" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
      <FormField
        control={control}
        name={name('forma_pago')}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{t('quotes:conditions.payment')}</FormLabel>
            <FormControl>
              <Input className="min-h-touch" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
      <FormField
        control={control}
        name={name('garantia')}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{t('quotes:conditions.warranty')}</FormLabel>
            <FormControl>
              <Input className="min-h-touch" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </fieldset>
  );
}
