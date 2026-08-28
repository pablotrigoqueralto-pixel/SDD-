import type { components } from '@/api/schema';

import { divisions, VASCULAR_ID } from './fixtures';

export type BrandRead = components['schemas']['BrandRead'];
export type LossReasonRead = components['schemas']['LossReasonRead'];
export type PipelineRead = components['schemas']['PipelineRead'];
export type PipelineStageRead = components['schemas']['PipelineStageRead'];
export type ReferenceDataRead = components['schemas']['ReferenceDataRead'];
export type JobTitleRead = components['schemas']['JobTitleRead'];
export type ProductFamilyRead = components['schemas']['ProductFamilyRead'];

const stamp = { created_at: '2026-08-28T07:00:00Z', updated_at: '2026-08-28T07:00:00Z' };

export const FERTIPRO_ID = '019000000-0000-7000-8000-0000000000b1';
export const HADECO_ID = '019000000-0000-7000-8000-0000000000b2';
export const COOK_ID = '019000000-0000-7000-8000-0000000000b3';
export const EQUIPMENT_ID = '019000000-0000-7000-8000-0000000000p1';
export const CONSUMABLES_ID = '019000000-0000-7000-8000-0000000000p2';

export const brands: BrandRead[] = [
  {
    id: FERTIPRO_ID,
    code: 'fertipro',
    name: 'Fertipro',
    is_own: true,
    is_active: true,
    division_ids: [],
    version: 1,
    ...stamp,
  },
  {
    id: HADECO_ID,
    code: 'hadeco',
    name: 'Hadeco',
    is_own: true,
    is_active: true,
    division_ids: [VASCULAR_ID],
    version: 3,
    ...stamp,
  },
  {
    id: COOK_ID,
    code: 'cook_medical',
    name: 'Cook Medical',
    is_own: false,
    is_active: false,
    division_ids: [],
    version: 1,
    ...stamp,
  },
];

export const lossReasons: LossReasonRead[] = [
  {
    id: '019000000-0000-7000-8000-0000000000r1',
    code: 'price',
    name_es: 'Precio',
    sort_order: 10,
    requires_brand: false,
    requires_note: false,
    is_active: true,
    version: 1,
    ...stamp,
  },
  {
    id: '019000000-0000-7000-8000-0000000000r2',
    code: 'competitor',
    name_es: 'Competidor',
    sort_order: 20,
    requires_brand: true,
    requires_note: false,
    is_active: true,
    version: 1,
    ...stamp,
  },
  {
    id: '019000000-0000-7000-8000-0000000000r6',
    code: 'other',
    name_es: 'Otro',
    sort_order: 60,
    requires_brand: false,
    requires_note: true,
    is_active: true,
    version: 1,
    ...stamp,
  },
];

function stage(
  id: string,
  code: string,
  name: string,
  order: number,
  probability: number,
  flags: Partial<Pick<PipelineStageRead, 'is_won' | 'is_lost' | 'is_at_risk' | 'is_active'>> = {},
): PipelineStageRead {
  return {
    id,
    code,
    name_es: name,
    sort_order: order,
    probability,
    is_won: false,
    is_lost: false,
    is_at_risk: false,
    is_active: true,
    version: 1,
    ...flags,
  };
}

export const pipelines: PipelineRead[] = [
  {
    id: EQUIPMENT_ID,
    code: 'equipment',
    name_es: 'Equipos',
    sort_order: 10,
    division_ids: [VASCULAR_ID],
    version: 2,
    ...stamp,
    stages: [
      stage('s-contact', 'contact', 'Contacto', 1, 10),
      stage('s-demo', 'demo', 'Demo', 2, 30),
      stage('s-quote', 'quote', 'Presupuesto', 3, 50),
      stage('s-won', 'won', 'Ganada', 4, 100, { is_won: true }),
      stage('s-lost', 'lost', 'Perdida', 5, 0, { is_lost: true }),
    ],
  },
  {
    id: CONSUMABLES_ID,
    code: 'consumables',
    name_es: 'Consumibles',
    sort_order: 20,
    division_ids: [],
    version: 1,
    ...stamp,
    stages: [
      stage('s-trial', 'trial', 'Prueba', 1, 20),
      stage('s-recurring', 'recurring', 'Recurrente', 2, 100, { is_won: true }),
      stage('s-risk', 'at_risk', 'En riesgo', 3, 100, { is_at_risk: true }),
    ],
  },
];

export const GYNAECOLOGIST_ID = '019000000-0000-7000-8000-0000000000j1';
export const PURCHASING_ID = '019000000-0000-7000-8000-0000000000j2';

export const jobTitles: JobTitleRead[] = [
  {
    id: GYNAECOLOGIST_ID,
    code: 'gynaecologist',
    name_es: 'Ginecólogo/a',
    sort_order: 10,
    is_active: true,
    version: 1,
    ...stamp,
  },
  {
    id: PURCHASING_ID,
    code: 'purchasing',
    name_es: 'Compras / suministros',
    sort_order: 80,
    is_active: true,
    version: 1,
    ...stamp,
  },
  {
    id: '019000000-0000-7000-8000-0000000000j3',
    code: 'other',
    name_es: 'Otro',
    sort_order: 110,
    is_active: false,
    version: 2,
    ...stamp,
  },
];

export const DOPPLERS_ID = '019000000-0000-7000-8000-0000000000f1';
export const EEG_ID = '019000000-0000-7000-8000-0000000000f2';
export const NEUROLOGY_ID = '019000000-0000-7000-8000-0000000000d2';

export const productFamilies: ProductFamilyRead[] = [
  {
    id: DOPPLERS_ID,
    code: 'dopplers',
    name_es: 'Dopplers',
    division_id: VASCULAR_ID,
    sort_order: 10,
    is_active: true,
    version: 1,
    ...stamp,
  },
  {
    id: '019000000-0000-7000-8000-0000000000f3',
    code: 'ecografos_vasculares',
    name_es: 'Ecógrafos vasculares',
    division_id: VASCULAR_ID,
    sort_order: 20,
    is_active: false,
    version: 2,
    ...stamp,
  },
  {
    id: EEG_ID,
    code: 'electroencefalografia',
    name_es: 'Electroencefalografía',
    division_id: NEUROLOGY_ID,
    sort_order: 10,
    is_active: true,
    version: 1,
    ...stamp,
  },
];

export const referenceBundle: ReferenceDataRead = {
  account_types: [
    {
      id: '019000000-0000-7000-8000-0000000000t1',
      code: 'ivf_clinic',
      name_es: 'Clínica FIV / laboratorio',
      sort_order: 10,
      buys_via_tender: false,
      is_active: true,
    },
    {
      id: '019000000-0000-7000-8000-0000000000t2',
      code: 'public_hospital',
      name_es: 'Hospital público',
      sort_order: 20,
      buys_via_tender: true,
      is_active: true,
    },
  ],
  activity_types: [
    {
      id: '019000000-0000-7000-8000-0000000000y1',
      code: 'visit',
      name_es: 'Visita',
      sort_order: 10,
      icon: 'map-pin',
      counts_as_contact: true,
      is_active: true,
    },
    {
      id: '019000000-0000-7000-8000-0000000000y2',
      code: 'call',
      name_es: 'Llamada',
      sort_order: 20,
      icon: 'phone',
      counts_as_contact: true,
      is_active: true,
    },
    {
      id: '019000000-0000-7000-8000-0000000000y6',
      code: 'note',
      name_es: 'Nota',
      sort_order: 60,
      icon: 'sticky-note',
      counts_as_contact: false,
      is_active: true,
    },
  ],
  divisions,
  brands,
  loss_reasons: lossReasons,
  pipelines,
  job_titles: jobTitles,
  product_families: productFamilies,
};
