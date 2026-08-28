import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type ProductFamilyRead = components['schemas']['ProductFamilyRead'];
export type ProductFamilyCreate = components['schemas']['ProductFamilyCreate'];
export type ProductFamilyUpdate = components['schemas']['ProductFamilyUpdate'];

export async function listProductFamilies(): Promise<ProductFamilyRead[]> {
  const { data } = await apiClient.get<ProductFamilyRead[]>('/product-families');
  return data;
}

export async function createProductFamily(
  payload: ProductFamilyCreate,
): Promise<ProductFamilyRead> {
  const { data } = await apiClient.post<ProductFamilyRead>('/product-families', payload);
  return data;
}

export async function updateProductFamily(
  id: string,
  version: number,
  payload: ProductFamilyUpdate,
): Promise<ProductFamilyRead> {
  const { data } = await apiClient.patch<ProductFamilyRead>(`/product-families/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}
