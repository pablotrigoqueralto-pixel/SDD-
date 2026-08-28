import type { components } from '@/api/schema';

import { VASCULAR_ID } from './fixtures';
import { COOK_ID, DOPPLERS_ID, EEG_ID, HADECO_ID, NEUROLOGY_ID } from './reference-fixtures';

export type ProductRead = components['schemas']['ProductRead'];

export const DOPPLER_ID = '019000000-0000-7000-8000-0000000000c1';
export const GEL_ID = '019000000-0000-7000-8000-0000000000c2';
export const SERVICE_ID = '019000000-0000-7000-8000-0000000000c3';
export const RETIRED_ID = '019000000-0000-7000-8000-0000000000c4';

const stamp = { created_at: '2026-08-28T07:00:00Z', updated_at: '2026-08-28T07:00:00Z' };

export const doppler: ProductRead = {
  id: DOPPLER_ID,
  sku: 'HAD-1000',
  name: 'Doppler ES-100',
  brand: { id: HADECO_ID, name: 'Hadeco', is_own: true },
  family: { id: DOPPLERS_ID, name: 'Dopplers', division_id: VASCULAR_ID },
  kind: 'equipment',
  list_price: '12500.00',
  cost_price: '8000.00',
  unit: 'ud',
  description: 'Doppler bidireccional',
  is_active: true,
  version: 1,
  ...stamp,
};

export const gel: ProductRead = {
  ...doppler,
  id: GEL_ID,
  sku: 'GEL-5L',
  name: 'Gel ultrasonidos 5 l',
  kind: 'consumable',
  list_price: '18.50',
  cost_price: null,
  description: null,
};

export const maintenance: ProductRead = {
  ...doppler,
  id: SERVICE_ID,
  sku: 'SRV-EEG',
  name: 'Mantenimiento EEG',
  brand: { id: COOK_ID, name: 'Cook Medical', is_own: false },
  family: { id: EEG_ID, name: 'Electroencefalografía', division_id: NEUROLOGY_ID },
  kind: 'service',
  list_price: '450.00',
  cost_price: '200.00',
  unit: 'h',
  description: null,
};

export const retired: ProductRead = {
  ...doppler,
  id: RETIRED_ID,
  sku: 'OLD-1',
  name: 'Doppler antiguo',
  is_active: false,
  version: 2,
};

export const products: ProductRead[] = [doppler, gel, maintenance, retired];
