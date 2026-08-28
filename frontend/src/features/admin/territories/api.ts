import { apiClient, ifMatch } from '@/api/client';

import type { Page, TerritoryCreate, TerritoryRead, TerritoryUpdate } from '../types';

export interface TerritoryListFilters {
  q?: string;
  is_active?: 'true' | 'false' | '';
  page?: number;
}

export async function listTerritories(
  filters: TerritoryListFilters = {},
): Promise<Page<TerritoryRead>> {
  const params: Record<string, string | number> = { page_size: 200 };
  if (filters.q) params.q = filters.q;
  if (filters.is_active) params.is_active = filters.is_active;
  if (filters.page) params.page = filters.page;
  const { data } = await apiClient.get<Page<TerritoryRead>>('/territories', { params });
  return data;
}

export async function getTerritory(id: string): Promise<TerritoryRead> {
  const { data } = await apiClient.get<TerritoryRead>(`/territories/${id}`);
  return data;
}

export async function createTerritory(payload: TerritoryCreate): Promise<TerritoryRead> {
  const { data } = await apiClient.post<TerritoryRead>('/territories', payload);
  return data;
}

export async function updateTerritory(
  id: string,
  version: number,
  payload: TerritoryUpdate,
): Promise<TerritoryRead> {
  const { data } = await apiClient.patch<TerritoryRead>(`/territories/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}
