import type { Control } from 'react-hook-form';
import { useFormContext, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';

import type { OpportunityInput } from '../schemas';

/** Tender toggle plus its three fields, shown only while the toggle is on. */
export function TenderFields() {
  const { t } = useTranslation();
  const { control } = useFormContext<OpportunityInput>();
  const isTender = useWatch({ control, name: 'is_tender' });

  return (
    <>
      <FormField
        control={control}
        name="is_tender"
        render={({ field }) => (
          <FormItem>
            <label className="flex min-h-touch items-center gap-3 text-sm">
              <input
                type="checkbox"
                className="size-5 accent-primary"
                checked={field.value}
                onChange={(event) => {
                  field.onChange(event.target.checked);
                }}
              />
              <span>{t('opportunities:form.tender')}</span>
            </label>
          </FormItem>
        )}
      />
      {isTender ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {textField(control, 'tender_reference', t('opportunities:form.tenderReference'))}
          {dateField(control, 'tender_deadline', t('opportunities:form.tenderDeadline'))}
          {dateField(control, 'estimated_award_date', t('opportunities:form.awardDate'))}
        </div>
      ) : null}
    </>
  );
}

function textField(control: Control<OpportunityInput>, name: 'tender_reference', label: string) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input className="min-h-touch" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

function dateField(
  control: Control<OpportunityInput>,
  name: 'tender_deadline' | 'estimated_award_date',
  label: string,
) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input className="min-h-touch" type="date" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}
