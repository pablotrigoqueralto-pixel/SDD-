import { apiClient } from '@/api/client';
import type { components } from '@/api/schema';

export type SearchResultsRead = components['schemas']['SearchResultsRead'];
export type AccountHitRead = components['schemas']['AccountHitRead'];
export type ContactHitRead = components['schemas']['ContactHitRead'];
export type OpportunityHitRead = components['schemas']['OpportunityHitRead'];
export type QuoteHitRead = components['schemas']['QuoteHitRead'];

export const SEARCH_MIN_LENGTH = 2;

export async function globalSearch(q: string): Promise<SearchResultsRead> {
  const { data } = await apiClient.get<SearchResultsRead>('/search', { params: { q } });
  return data;
}
