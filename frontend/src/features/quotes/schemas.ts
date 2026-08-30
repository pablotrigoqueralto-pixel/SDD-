import { z } from 'zod';

import { parsePrice } from '@/features/catalogue';

export const VAT_RATES = ['21', '10', '4', '0'] as const;

export const quoteLineSchema = z
  .object({
    product_id: z.string(),
    description: z.string().trim().min(1, 'quotes:lines.descriptionRequired').max(300),
    quantity: z
      .string()
      .trim()
      .min(1, 'quotes:lines.quantityRequired')
      .refine((value) => {
        const parsed = parsePrice(value);
        return parsed !== null && Number(parsed) > 0;
      }, 'quotes:lines.quantityRequired'),
    unit_price: z
      .string()
      .trim()
      .refine((value) => value === '' || parsePrice(value) !== null, 'catalogue:form.priceInvalid'),
    discount_percent: z
      .string()
      .trim()
      .refine((value) => {
        if (value === '') return true;
        const parsed = parsePrice(value);
        return parsed !== null && Number(parsed) >= 0 && Number(parsed) <= 100;
      }, 'quotes:lines.discountInvalid'),
    vat_rate: z.enum(VAT_RATES),
  })
  .refine((line) => line.product_id !== '' || line.unit_price !== '', {
    message: 'quotes:lines.priceRequired',
    path: ['unit_price'],
  });

export type QuoteLineFormValues = z.infer<typeof quoteLineSchema>;

export const quoteConditionsSchema = z.object({
  validez_dias: z
    .string()
    .trim()
    .min(1, 'quotes:conditions.validityRequired')
    .refine(
      (value) => /^\d+$/.test(value) && Number(value) >= 1,
      'quotes:conditions.validityRequired',
    ),
  plazo_entrega: z.string().trim().max(200),
  forma_pago: z.string().trim().max(200),
  garantia: z.string().trim().max(200),
});

export type QuoteConditionsFormValues = z.infer<typeof quoteConditionsSchema>;

export const quoteFormSchema = z.object({
  contact_id: z.string(),
  lines: z.array(quoteLineSchema).min(1, 'quotes:lines.atLeastOne'),
  conditions: quoteConditionsSchema,
});

export type QuoteFormValues = z.infer<typeof quoteFormSchema>;

export const sendQuoteSchema = z
  .object({
    recipients: z.array(z.string().trim().email('quotes:send.emailInvalid')),
    subject: z.string().trim().min(1, 'quotes:send.subjectRequired').max(300),
    body: z.string().trim().min(1, 'quotes:send.bodyRequired').max(10000),
    valid_until: z.string(),
    skip_email: z.boolean(),
  })
  .refine((values) => values.skip_email || values.recipients.length > 0, {
    message: 'quotes:send.recipientsRequired',
    path: ['recipients'],
  });

export type SendQuoteFormValues = z.infer<typeof sendQuoteSchema>;

export const rejectQuoteSchema = z.object({
  note: z.string().trim().max(2000),
});

export type RejectQuoteFormValues = z.infer<typeof rejectQuoteSchema>;

export const quoteSettingsSchema = z.object({
  conditions: quoteConditionsSchema,
  subject: z.string().trim().min(1, 'quotes:settings.subjectRequired').max(300),
  body: z.string().trim().min(1, 'quotes:settings.bodyRequired').max(10000),
});

export type QuoteSettingsFormValues = z.infer<typeof quoteSettingsSchema>;

/** {numero}/{centro}/{comercial} placeholders → real values, keeping unknown ones. */
export function interpolateTemplate(
  template: string,
  values: { numero: string; centro: string; comercial: string },
): string {
  return template
    .replaceAll('{numero}', values.numero)
    .replaceAll('{centro}', values.centro)
    .replaceAll('{comercial}', values.comercial);
}

/** yyyy-MM-dd for a date input, from an ISO date string. */
export function toDateInput(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : '';
}
