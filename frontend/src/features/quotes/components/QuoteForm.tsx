import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

import { NativeSelect } from '@/components/shared/NativeSelect';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { parsePrice } from '@/features/catalogue';
import { useAccountContacts } from '@/features/contacts';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { QuoteDetail, QuoteLineWrite } from '../api';
import { useSeesQuoteCost } from '../hooks';
import { useUpdateQuote } from '../queries';
import { quoteFormSchema, type QuoteFormValues } from '../schemas';
import { computeQuoteTotals } from '../totals';
import { ConditionsFields } from './ConditionsFields';
import { QuoteLinesEditor } from './QuoteLinesEditor';
import { TotalsBox } from './TotalsBox';

interface QuoteFormProps {
  quote: QuoteDetail;
  onSaved: () => void;
}

function toFormValues(quote: QuoteDetail): QuoteFormValues {
  return {
    contact_id: quote.contact_id ?? '',
    lines: quote.lines.map((line) => ({
      product_id: line.product_id ?? '',
      description: line.description,
      quantity: line.quantity,
      unit_price: line.unit_price,
      discount_percent: line.discount_percent,
      vat_rate: line.vat_rate.replace(/\.00$/, '') as QuoteFormValues['lines'][number]['vat_rate'],
    })),
    conditions: {
      validez_dias: String(quote.conditions.validez_dias),
      plazo_entrega: quote.conditions.plazo_entrega ?? '',
      forma_pago: quote.conditions.forma_pago ?? '',
      garantia: quote.conditions.garantia ?? '',
    },
  };
}

/** Draft editing: lines with live totals, conditions and the contact. */
export function QuoteForm({ quote, onSaved }: QuoteFormProps) {
  const { t } = useTranslation();
  const updateQuote = useUpdateQuote();
  const contacts = useAccountContacts(quote.account_id);
  const seesCost = useSeesQuoteCost();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<QuoteFormValues>({
    resolver: zodResolver(quoteFormSchema),
    defaultValues: toFormValues(quote),
  });

  const watchedLines = useWatch({ control: form.control, name: 'lines' });
  const totals = computeQuoteTotals(
    watchedLines.map((line) => ({
      quantity: line.quantity,
      unit_price: line.unit_price,
      discount_percent: line.discount_percent || '0',
      vat_rate: line.vat_rate,
    })),
  );

  const handleSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    const lines: QuoteLineWrite[] = values.lines.map((line) => ({
      description: line.description,
      quantity: parsePrice(line.quantity) ?? '1.00',
      discount_percent: parsePrice(line.discount_percent || '0') ?? '0.00',
      vat_rate: line.vat_rate,
      ...(line.product_id ? { product_id: line.product_id } : {}),
      ...(line.unit_price ? { unit_price: parsePrice(line.unit_price) ?? '0.00' } : {}),
    }));
    try {
      await updateQuote.mutateAsync({
        id: quote.id,
        version: quote.version,
        accountId: quote.account_id,
        opportunityId: quote.opportunity_id,
        payload: {
          contact_id: values.contact_id || null,
          conditions: {
            validez_dias: Number(values.conditions.validez_dias),
            plazo_entrega: values.conditions.plazo_entrega || null,
            forma_pago: values.conditions.forma_pago || null,
            garantia: values.conditions.garantia || null,
          },
          lines,
        },
      });
      onSaved();
    } catch (error) {
      const problem = toProblem(error);
      setFormError(
        isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
      );
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <FormField
          control={form.control}
          name="contact_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('quotes:sheet.contact')}</FormLabel>
              <FormControl>
                <NativeSelect {...field}>
                  <option value="">{t('quotes:sheet.contact')}</option>
                  {contacts.data?.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {contact.first_name} {contact.last_name}
                    </option>
                  ))}
                </NativeSelect>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <QuoteLinesEditor control={form.control} />
        <TotalsBox
          totalBase={totals.totalBase}
          breakdown={totals.breakdown}
          total={totals.total}
          {...(seesCost && 'total_margin' in quote ? { margin: quote.total_margin } : {})}
        />
        <ConditionsFields control={form.control} prefix="conditions" />
        {formError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {t(formError)}
          </p>
        ) : null}
        <Button type="submit" className="min-h-touch" disabled={updateQuote.isPending}>
          {t('actions.save')}
        </Button>
      </form>
    </Form>
  );
}
