import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type QuoteRead = components['schemas']['QuoteRead'];
export type QuotePublicRead = components['schemas']['QuotePublicRead'];
export type QuoteSummaryRead = components['schemas']['QuoteSummaryRead'];
export type QuoteLineRead = components['schemas']['QuoteLineRead'];
export type QuoteVersionRead = components['schemas']['QuoteVersionRead'];
export type QuoteConditionsRead = components['schemas']['QuoteConditionsRead'];
export type QuoteStatus = components['schemas']['QuoteStatus'];
export type QuoteSettingsRead = components['schemas']['QuoteSettingsRead'];
export type QuoteSettingsUpdate = components['schemas']['QuoteSettingsUpdate'];

/** The API hides cost fields from reps and back office; treat them as optional. */
export type QuoteDetail = QuoteRead | QuotePublicRead;

export interface QuotePage {
  items: QuoteSummaryRead[];
  total: number;
  page: number;
  page_size: number;
}

export interface QuoteListFilters {
  status?: QuoteStatus | 'all';
  owner_id?: string;
  opportunity_id?: string;
  account_id?: string;
  expiring?: boolean;
  q?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface QuoteLineWrite {
  description: string;
  quantity: string;
  unit_price?: string;
  discount_percent?: string;
  vat_rate?: string;
  product_id?: string | null;
}

export interface QuoteConditionsWrite {
  validez_dias: number;
  plazo_entrega?: string | null;
  forma_pago?: string | null;
  garantia?: string | null;
}

export interface QuoteUpdatePayload {
  contact_id?: string | null;
  conditions?: QuoteConditionsWrite;
  valid_until?: string | null;
  lines?: QuoteLineWrite[];
}

export interface QuoteSendPayload {
  recipients: { email: string; name?: string | null }[];
  subject: string;
  body: string;
  valid_until?: string;
  skip_email: boolean;
}

function params(filters: object): Record<string, string | number | boolean> {
  const cleaned: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '' && value !== null && value !== false) {
      cleaned[key] = value as string | number | boolean;
    }
  }
  return cleaned;
}

export async function listQuotes(filters: QuoteListFilters): Promise<QuotePage> {
  const { data } = await apiClient.get<QuotePage>('/quotes', { params: params(filters) });
  return data;
}

export async function listOpportunityQuotes(opportunityId: string): Promise<QuoteSummaryRead[]> {
  const { data } = await apiClient.get<QuoteSummaryRead[]>(
    `/opportunities/${opportunityId}/quotes`,
  );
  return data;
}

export async function getQuote(id: string): Promise<QuoteDetail> {
  const { data } = await apiClient.get<QuoteDetail>(`/quotes/${id}`);
  return data;
}

export async function createQuote(payload: {
  opportunity_id: string;
  contact_id?: string;
}): Promise<QuoteDetail> {
  const { data } = await apiClient.post<QuoteDetail>('/quotes', payload);
  return data;
}

export async function updateQuote(
  id: string,
  version: number,
  payload: QuoteUpdatePayload,
): Promise<QuoteDetail> {
  const { data } = await apiClient.patch<QuoteDetail>(`/quotes/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function deleteQuote(id: string): Promise<void> {
  await apiClient.delete(`/quotes/${id}`);
}

export async function sendQuote(
  id: string,
  version: number,
  payload: QuoteSendPayload,
): Promise<QuoteDetail> {
  const { data } = await apiClient.post<QuoteDetail>(`/quotes/${id}/send`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function acceptQuote(
  id: string,
  version: number,
  payload: { occurred_on?: string },
): Promise<QuoteDetail> {
  const { data } = await apiClient.post<QuoteDetail>(`/quotes/${id}/accept`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function rejectQuote(
  id: string,
  version: number,
  payload: { note?: string },
): Promise<QuoteDetail> {
  const { data } = await apiClient.post<QuoteDetail>(`/quotes/${id}/reject`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function reviseQuote(id: string, version: number): Promise<QuoteDetail> {
  const { data } = await apiClient.post<QuoteDetail>(
    `/quotes/${id}/revise`,
    {},
    { headers: ifMatch(version) },
  );
  return data;
}

export async function retryQuoteEmail(id: string): Promise<QuoteDetail> {
  const { data } = await apiClient.post<QuoteDetail>(`/quotes/${id}/retry-email`);
  return data;
}

/** The PDF needs the JWT, so a plain <a href> cannot download it. */
export async function fetchQuotePdf(id: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/quotes/${id}/pdf`, { responseType: 'blob' });
  return data;
}

export async function getQuoteSettings(): Promise<QuoteSettingsRead> {
  const { data } = await apiClient.get<QuoteSettingsRead>('/quote-settings');
  return data;
}

export async function updateQuoteSettings(
  payload: QuoteSettingsUpdate,
): Promise<QuoteSettingsRead> {
  const { data } = await apiClient.put<QuoteSettingsRead>('/quote-settings', payload);
  return data;
}
