import type { components } from '@/api/schema';

import { TAMBRE_ID } from './accounts-fixtures';
import { REP_ID } from './fixtures';
import { OPP_ID } from './opportunities-fixtures';

export type QuoteRead = components['schemas']['QuoteRead'];
export type QuoteSummaryRead = components['schemas']['QuoteSummaryRead'];
export type QuoteSettingsRead = components['schemas']['QuoteSettingsRead'];

export const QUOTE_DRAFT_ID = '019000000-0000-7000-8000-0000000000q1';
export const QUOTE_SENT_ID = '019000000-0000-7000-8000-0000000000q2';
export const QUOTE_EXPIRED_ID = '019000000-0000-7000-8000-0000000000q3';

const stamp = { created_at: '2026-08-27T09:00:00Z', updated_at: '2026-08-27T09:00:00Z' };

const conditions = {
  validez_dias: 30,
  plazo_entrega: '4-6 semanas',
  forma_pago: 'Transferencia a 30 días',
  garantia: '2 años',
};

export const draftQuote: QuoteRead = {
  id: QUOTE_DRAFT_ID,
  opportunity_id: OPP_ID,
  opportunity_name: 'Clínica Tambre · Vascular · agosto 2026',
  account_id: TAMBRE_ID,
  account_name: 'Clínica Tambre',
  quote_number: 'P-2026-0001',
  display_number: 'P-2026-0001',
  revision: 1,
  status: 'draft',
  owner_id: REP_ID,
  owner_name: 'Ana García',
  contact_id: null,
  conditions,
  total_base: '26000.00',
  total_vat: '5460.00',
  total: '31460.00',
  total_margin: '8000.00',
  vat_breakdown: [{ rate: '21.00', base: '26000.00', vat: '5460.00' }],
  valid_until: null,
  is_expired: false,
  sent_at: null,
  accepted_at: null,
  rejected_at: null,
  rejection_note: null,
  superseded_at: null,
  versions: [{ id: QUOTE_DRAFT_ID, revision: 1, status: 'draft', sent_at: null }],
  email_status: null,
  email_error: null,
  version: 1,
  lines: [
    {
      id: 'quote-line-1',
      product_id: 'product-doppler-id',
      product_code: 'DP-3000',
      description: 'Doppler vascular DP-3000',
      quantity: '2.00',
      unit_price: '13000.00',
      discount_percent: '0.00',
      vat_rate: '21.00',
      unit_cost: '9000.00',
      base: '26000.00',
      vat: '5460.00',
      position: 0,
    },
  ],
  ...stamp,
};

export const sentQuote: QuoteRead = {
  ...draftQuote,
  id: QUOTE_SENT_ID,
  quote_number: 'P-2026-0002',
  display_number: 'P-2026-0002',
  status: 'sent',
  sent_at: '2026-08-27T10:00:00Z',
  valid_until: '2026-09-26',
  email_status: 'sent',
  versions: [{ id: QUOTE_SENT_ID, revision: 1, status: 'sent', sent_at: '2026-08-27T10:00:00Z' }],
  version: 2,
};

export const expiredQuote: QuoteRead = {
  ...sentQuote,
  id: QUOTE_EXPIRED_ID,
  quote_number: 'P-2026-0003',
  display_number: 'P-2026-0003',
  valid_until: '2026-08-20',
  is_expired: true,
  email_status: 'failed',
  email_error: 'Graph sendMail returned 500',
  versions: [
    { id: QUOTE_EXPIRED_ID, revision: 1, status: 'sent', sent_at: '2026-08-27T10:00:00Z' },
  ],
};

export function summaryOfQuote(quote: QuoteRead): QuoteSummaryRead {
  return {
    id: quote.id,
    opportunity_id: quote.opportunity_id,
    opportunity_name: quote.opportunity_name,
    account_id: quote.account_id,
    account_name: quote.account_name,
    quote_number: quote.quote_number,
    display_number: quote.display_number,
    revision: quote.revision,
    status: quote.status,
    total: quote.total,
    valid_until: quote.valid_until,
    is_expired: quote.is_expired,
    owner_id: quote.owner_id,
    owner_name: quote.owner_name,
    version: quote.version,
    sent_at: quote.sent_at,
    created_at: quote.created_at,
    updated_at: quote.updated_at,
  };
}

export const quotes: QuoteRead[] = [draftQuote, sentQuote, expiredQuote];

export const quoteSettings: QuoteSettingsRead = {
  conditions_defaults: conditions,
  email_template: {
    subject: 'Presupuesto {numero} - Quermed',
    body: 'Adjuntamos el presupuesto {numero} para {centro}.\n\nUn saludo,\n{comercial}',
  },
};
