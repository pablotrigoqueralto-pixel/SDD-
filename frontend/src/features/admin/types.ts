import type { components } from '@/api/schema';

export type UserRead = components['schemas']['UserRead'];
export type UserCreate = components['schemas']['UserCreate'];
export type UserUpdate = components['schemas']['UserUpdate'];
export type Role = components['schemas']['Role'];
export type TerritoryRead = components['schemas']['TerritoryRead'];
export type TerritoryCreate = components['schemas']['TerritoryCreate'];
export type TerritoryUpdate = components['schemas']['TerritoryUpdate'];
export type DivisionRead = components['schemas']['DivisionRead'];

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const ROLES: Role[] = ['sales_rep', 'sales_manager', 'back_office', 'admin'];
