import { apiClient, ifMatch } from '@/api/client';

import type { Page, Role, UserCreate, UserRead, UserUpdate } from '../types';

export interface UserListFilters {
  q?: string | undefined;
  role?: Role | '' | undefined;
  is_active?: 'true' | 'false' | '' | undefined;
  page?: number | undefined;
  page_size?: number | undefined;
  sort?: string | undefined;
}

export async function listUsers(filters: UserListFilters): Promise<Page<UserRead>> {
  const params: Record<string, string | number> = {};
  if (filters.q) params.q = filters.q;
  if (filters.role) params.role = filters.role;
  if (filters.is_active) params.is_active = filters.is_active;
  if (filters.page) params.page = filters.page;
  if (filters.page_size) params.page_size = filters.page_size;
  if (filters.sort) params.sort = filters.sort;
  const { data } = await apiClient.get<Page<UserRead>>('/users', { params });
  return data;
}

export async function getUser(id: string): Promise<UserRead> {
  const { data } = await apiClient.get<UserRead>(`/users/${id}`);
  return data;
}

export async function createUser(payload: UserCreate): Promise<UserRead> {
  const { data } = await apiClient.post<UserRead>('/users', payload);
  return data;
}

export async function updateUser(
  id: string,
  version: number,
  payload: UserUpdate,
): Promise<UserRead> {
  const { data } = await apiClient.patch<UserRead>(`/users/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}
