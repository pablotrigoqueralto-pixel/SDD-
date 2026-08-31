import type { components } from '@/api/schema';

import { CENTRO_ID, REP_ID, VASCULAR_ID } from './fixtures';
import { GYNAECOLOGIST_ID } from './reference-fixtures';

export type AccountRead = components['schemas']['AccountRead'];
export type AccountSummaryRead = components['schemas']['AccountSummaryRead'];
export type ContactRead = components['schemas']['ContactRead'];

const stamp = { created_at: '2026-08-28T08:00:00Z', updated_at: '2026-08-28T08:00:00Z' };

export const IVF_TYPE_ID = '019000000-0000-7000-8000-0000000000t1';
export const HOSPITAL_TYPE_ID = '019000000-0000-7000-8000-0000000000t2';
export const TAMBRE_ID = '019000000-0000-7000-8000-0000000000c1';
export const LA_PAZ_ID = '019000000-0000-7000-8000-0000000000c2';
export const ANA_ID = '019000000-0000-7000-8000-0000000000k1';
export const BEA_ID = '019000000-0000-7000-8000-0000000000k2';

export const tambre: AccountRead = {
  id: TAMBRE_ID,
  name: 'Clínica Tambre',
  account_type_id: IVF_TYPE_ID,
  province_code: '28',
  street: 'Calle Tambre 8',
  postal_code: '28002',
  city: 'Madrid',
  tax_id: 'B12345674',
  phones: [
    { label: 'Centralita', number: '+34911234567', extension: null, note: null },
    { label: 'Secretaría', number: '+34911234568', extension: '4021', note: null },
  ],
  billing_notes: 'Factura por FACe · contabilidad@tambre.es',
  email: 'info@tambre.es',
  website: null,
  customer_code: 'C-0001',
  notes: 'Cliente histórico',
  territory_id: CENTRO_ID,
  territory_name: 'Centro',
  owner_id: REP_ID,
  owner_name: 'Ana García',
  territory_mismatch: false,
  division_ids: [VASCULAR_ID],
  brand_ids: [],
  addresses: [
    {
      label: 'Laboratorio',
      street: 'Calle Tambre 10',
      postal_code: '28002',
      city: 'Madrid',
      province_code: '28',
      notes: null,
    },
  ],
  last_contact_at: '2026-08-27T09:00:00Z',
  next_activity_at: null,
  is_active: true,
  version: 3,
  ...stamp,
};

export const laPaz: AccountRead = {
  ...tambre,
  id: LA_PAZ_ID,
  name: 'Hospital La Paz',
  account_type_id: HOSPITAL_TYPE_ID,
  province_code: '08',
  street: null,
  postal_code: null,
  city: 'Barcelona',
  tax_id: null,
  phones: [],
  billing_notes: null,
  email: null,
  customer_code: null,
  notes: null,
  owner_id: null,
  owner_name: null,
  territory_mismatch: true,
  division_ids: [],
  addresses: [],
  last_contact_at: null,
  next_activity_at: null,
  version: 1,
};

export function summaryOf(account: AccountRead, primaryContact: string | null): AccountSummaryRead {
  return {
    id: account.id,
    name: account.name,
    account_type_id: account.account_type_id,
    city: account.city,
    province_code: account.province_code,
    primary_phone: account.phones[0]?.number ?? null,
    territory_id: account.territory_id,
    territory_name: account.territory_name,
    owner_id: account.owner_id,
    owner_name: account.owner_name,
    is_active: account.is_active,
    territory_mismatch: account.territory_mismatch,
    primary_contact_name: primaryContact,
    last_contact_at: account.last_contact_at,
    next_activity_at: account.next_activity_at,
    updated_at: account.updated_at,
  };
}

export const accounts: AccountRead[] = [tambre, laPaz];

export const ana: ContactRead = {
  id: ANA_ID,
  account_id: TAMBRE_ID,
  account_name: 'Clínica Tambre',
  first_name: 'Ana',
  last_name: 'Pérez',
  job_title_id: GYNAECOLOGIST_ID,
  division_id: VASCULAR_ID,
  email: 'ana@tambre.es',
  phones: [{ label: 'Móvil', number: '+34612345678', extension: null, note: null }],
  is_head_of_department: false,
  preferred_channel: 'phone',
  notes: null,
  is_primary: true,
  is_active: true,
  consent: {
    status: 'granted',
    at: '2026-08-28T10:00:00Z',
    source: 'verbal',
    recorded_by: REP_ID,
  },
  anonymised_at: null,
  version: 1,
  ...stamp,
};

export const bea: ContactRead = {
  ...ana,
  id: BEA_ID,
  first_name: 'Bea',
  last_name: 'Ruiz',
  job_title_id: null,
  division_id: null,
  email: null,
  phones: [{ label: 'Fijo', number: '+34911234567', extension: null, note: null }],
  is_head_of_department: true,
  preferred_channel: 'phone',
  is_primary: false,
  consent: { status: 'unknown', at: null, source: null, recorded_by: null },
};

export const contacts: ContactRead[] = [ana, bea];
