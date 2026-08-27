import { HttpResponse } from 'msw';

import type { components } from '@/api/schema';

export type UserRead = components['schemas']['UserRead'];
export type MeRead = components['schemas']['MeRead'];
export type TerritoryRead = components['schemas']['TerritoryRead'];
export type DivisionRead = components['schemas']['DivisionRead'];

export const ADMIN_ID = '019000000-0000-7000-8000-000000000001';
export const REP_ID = '019000000-0000-7000-8000-000000000002';
export const CENTRO_ID = '019000000-0000-7000-8000-0000000000a1';
export const VASCULAR_ID = '019000000-0000-7000-8000-0000000000d1';

export const adminUser: UserRead = {
  id: ADMIN_ID,
  email: 'admin@quermed.com',
  full_name: 'Alicia Admin',
  role: 'admin',
  is_active: true,
  identity_provider: 'password',
  territory_ids: [],
  division_ids: [],
  version: 1,
  created_at: '2026-08-27T10:00:00Z',
  updated_at: '2026-08-27T10:00:00Z',
};

export const repUser: UserRead = {
  ...adminUser,
  id: REP_ID,
  email: 'ana@quermed.com',
  full_name: 'Ana García',
  role: 'sales_rep',
  territory_ids: [CENTRO_ID],
  division_ids: [VASCULAR_ID],
};

export const territories: TerritoryRead[] = [
  {
    id: CENTRO_ID,
    name: 'Centro',
    provinces: ['28', '45'],
    is_active: true,
    user_count: 1,
    version: 1,
    created_at: '2026-08-27T10:00:00Z',
    updated_at: '2026-08-27T10:00:00Z',
  },
];

export const divisions: DivisionRead[] = [
  { id: VASCULAR_ID, code: 'vascular', name_es: 'Vascular', sort_order: 40 },
  {
    id: '019000000-0000-7000-8000-0000000000d2',
    code: 'neurology',
    name_es: 'Neurología',
    sort_order: 50,
  },
];

export function page<T>(items: T[]): {
  items: T[];
  total: number;
  page: number;
  page_size: number;
} {
  return { items, total: items.length, page: 1, page_size: 50 };
}

export function problem(
  status: number,
  code: string,
  detail: string,
  errors: { field: string; message: string; code: string }[] = [],
): Response {
  return HttpResponse.json(
    {
      type: `https://crm.quermed.com/problems/${code.replace(/_/g, '-')}`,
      title: code,
      status,
      detail,
      code,
      trace_id: 'test-trace',
      ...(errors.length ? { errors } : {}),
    },
    { status, headers: { 'Content-Type': 'application/problem+json' } },
  );
}
