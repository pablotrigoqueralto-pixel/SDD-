import { z } from 'zod';

import { parsePrice } from '@/features/catalogue';

const amountText = (requiredMessage: string) =>
  z
    .string()
    .trim()
    .min(1, requiredMessage)
    .refine((value) => parsePrice(value) !== null, 'opportunities:form.amountInvalid');

export const opportunitySchema = z.object({
  account_id: z.string().min(1, 'opportunities:form.accountRequired'),
  division_id: z.string().min(1, 'opportunities:form.divisionRequired'),
  estimated_amount: amountText('opportunities:form.amountRequired'),
  name: z.string().trim().max(200),
  description: z.string().trim().max(2000),
  expected_close_date: z.string(),
  owner_id: z.string(),
  is_tender: z.boolean(),
  tender_reference: z.string().trim().max(100),
  tender_deadline: z.string(),
  estimated_award_date: z.string(),
});

export type OpportunityInput = z.infer<typeof opportunitySchema>;

export const winSchema = z.object({
  won_amount: amountText('opportunities:form.amountRequired'),
  won_at: z.string(),
});

export type WinInput = z.infer<typeof winSchema>;

export const loseSchema = z.object({
  loss_reason_id: z.string().min(1, 'opportunities:lose.reasonRequired'),
  competitor_brand_id: z.string(),
  note: z.string().trim().max(2000),
});

export type LoseInput = z.infer<typeof loseSchema>;

export const lineSchema = z.object({
  product_id: z.string().min(1, 'opportunities:lines.productRequired'),
  quantity: z
    .string()
    .trim()
    .min(1, 'opportunities:lines.quantityRequired')
    .refine((value) => {
      const parsed = parsePrice(value);
      return parsed !== null && Number(parsed) > 0;
    }, 'opportunities:lines.quantityRequired'),
  unit_price: z
    .string()
    .trim()
    .refine((value) => value === '' || parsePrice(value) !== null, 'catalogue:form.priceInvalid'),
});

export type LineInput = z.infer<typeof lineSchema>;

/** yyyy-MM-dd for a date input, from an ISO date string. */
export function toDateInput(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : '';
}
