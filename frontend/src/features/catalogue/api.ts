import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type ProductRead = components['schemas']['ProductRead'];
export type ProductPublicRead = components['schemas']['ProductPublicRead'];
export type ProductSummaryRead = components['schemas']['ProductSummaryRead'];
export type ProductSummaryPublicRead = components['schemas']['ProductSummaryPublicRead'];
export type ProductCreate = components['schemas']['ProductCreate'];
export type ProductUpdate = components['schemas']['ProductUpdate'];
export type ProductKind = components['schemas']['ProductKind'];

/** The API omits `cost_price` for roles that cannot see it; the UI treats it as optional. */
export type ProductSummary = ProductSummaryPublicRead & { cost_price?: string | null };
export type Product = ProductPublicRead & { cost_price?: string | null };

export interface ProductPage {
  items: ProductSummary[];
  total: number;
  page: number;
  page_size: number;
}

export const PRODUCT_KINDS: ProductKind[] = ['equipment', 'consumable', 'service'];

export interface ProductListFilters {
  q?: string;
  division_id?: string;
  family_id?: string;
  brand_id?: string;
  kind?: ProductKind;
  own?: boolean;
  /** Only managers and admins may ask for `false` or `all`. */
  is_active?: 'true' | 'false' | 'all';
  sort?: string;
  page?: number;
  page_size?: number;
}

export async function listProducts(filters: ProductListFilters): Promise<ProductPage> {
  const params: Record<string, string | number | boolean> = {};
  const entries = Object.entries(filters) as [string, string | number | boolean | undefined][];
  for (const [key, value] of entries) {
    if (value !== undefined && value !== '') params[key] = value;
  }
  const { data } = await apiClient.get<ProductPage>('/products', { params });
  return data;
}

export async function getProduct(id: string): Promise<Product> {
  const { data } = await apiClient.get<Product>(`/products/${id}`);
  return data;
}

export async function createProduct(payload: ProductCreate): Promise<Product> {
  const { data } = await apiClient.post<Product>('/products', payload);
  return data;
}

export async function updateProduct(
  id: string,
  version: number,
  payload: ProductUpdate,
): Promise<Product> {
  const { data } = await apiClient.patch<Product>(`/products/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function setProductActive(
  id: string,
  version: number,
  active: boolean,
): Promise<Product> {
  const action = active ? 'activate' : 'deactivate';
  const { data } = await apiClient.post<Product>(`/products/${id}/${action}`, undefined, {
    headers: ifMatch(version),
  });
  return data;
}
