import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type BrandRead = components['schemas']['BrandRead'];
export type BrandCreate = components['schemas']['BrandCreate'];
export type BrandUpdate = components['schemas']['BrandUpdate'];

export interface BrandFilters {
  q?: string | undefined;
  is_own?: 'true' | 'false' | '' | undefined;
}

export async function listBrands(filters: BrandFilters = {}): Promise<BrandRead[]> {
  const params: Record<string, string> = {};
  if (filters.q) params.q = filters.q;
  if (filters.is_own) params.is_own = filters.is_own;
  const { data } = await apiClient.get<BrandRead[]>('/brands', { params });
  return data;
}

export async function createBrand(payload: BrandCreate): Promise<BrandRead> {
  const { data } = await apiClient.post<BrandRead>('/brands', payload);
  return data;
}

export async function updateBrand(
  id: string,
  version: number,
  payload: BrandUpdate,
): Promise<BrandRead> {
  const { data } = await apiClient.patch<BrandRead>(`/brands/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}
