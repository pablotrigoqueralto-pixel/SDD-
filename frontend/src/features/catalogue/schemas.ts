import { z } from 'zod';

import { PRODUCT_KINDS } from './api';

const PRICE_PATTERN = /^\d{1,10}([.,]\d{1,2})?$/;

/**
 * Parse a price typed the Spanish way ("1.250,50") or the API way ("1250.50") into the
 * two-decimal string the API expects. Returns null when the text is not a price.
 */
export function parsePrice(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  // "13.000" / "1.250.000": Spanish thousands grouping without decimals
  if (/^\d{1,3}(\.\d{3})+$/.test(text)) return `${Number(text.replace(/\./g, ''))}.00`;
  const lastComma = text.lastIndexOf(',');
  const lastDot = text.lastIndexOf('.');
  let normalised: string;
  if (lastComma > lastDot) {
    // "1.250,50" → thousands dots, decimal comma
    normalised = text.replace(/\./g, '').replace(',', '.');
  } else if (lastDot > lastComma) {
    // "1,250.50" → thousands commas, decimal dot (or plain "1250.50")
    normalised = text.replace(/,/g, '');
  } else {
    normalised = text;
  }
  if (!PRICE_PATTERN.test(normalised)) return null;
  const [whole, fraction = ''] = normalised.split('.');
  return `${Number(whole)}.${fraction.padEnd(2, '0')}`;
}

const euroFormatter = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** "12500.00" → "12.500,00 €" */
export function formatPrice(value: string | number): string {
  return euroFormatter.format(typeof value === 'number' ? value : Number(value));
}

/** API price → text for the input ("12500.00" → "12500,00"). */
export function priceToInput(value: string | null | undefined): string {
  return value ? value.replace('.', ',') : '';
}

const priceText = (requiredMessage: string) =>
  z
    .string()
    .trim()
    .min(1, requiredMessage)
    .refine((value) => parsePrice(value) !== null, 'catalogue:form.priceInvalid');

const optionalPriceText = z
  .string()
  .trim()
  .refine((value) => value === '' || parsePrice(value) !== null, 'catalogue:form.priceInvalid');

export const productSchema = z.object({
  sku: z.string().trim().min(1, 'catalogue:form.skuRequired').max(50),
  name: z.string().trim().min(1, 'catalogue:form.nameRequired').max(200),
  brand_id: z.string().min(1, 'catalogue:form.brandRequired'),
  family_id: z.string().min(1, 'catalogue:form.familyRequired'),
  kind: z.string().refine((value) => (PRODUCT_KINDS as string[]).includes(value), {
    message: 'catalogue:form.kindRequired',
  }),
  list_price: priceText('catalogue:form.priceRequired'),
  cost_price: optionalPriceText,
  unit: z.string().trim().max(20),
  description: z.string().trim().max(2000),
  is_active: z.boolean(),
});

export type ProductInput = z.infer<typeof productSchema>;
