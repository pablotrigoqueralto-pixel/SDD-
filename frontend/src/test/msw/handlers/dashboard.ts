import { http, HttpResponse } from 'msw';

import type { components } from '@/api/schema';

import { TAMBRE_ID } from '../accounts-fixtures';
import { API_V1 } from '../constants';

type DashboardRead = components['schemas']['DashboardRead'];
type DashboardPeriod = components['schemas']['DashboardPeriod'];

export const NEGLECTED_ACCOUNT_ID = TAMBRE_ID;

export function dashboardPayload(period: DashboardPeriod = 'month'): DashboardRead {
  return {
    period: {
      period,
      start: '2026-08-01',
      end: '2026-09-01',
      previous_start: '2026-07-01',
      previous_end: '2026-08-01',
    },
    summary: {
      won: { amount: '30000.00', count: 3, previous_amount: '20000.00', previous_count: 2 },
      conversion: { rate: 0.6, won: 3, closed: 5, previous_rate: 0.5 },
      forecast: { amount: '4914.00', count: 2 },
      open_pipeline: { amount: '52000.00', count: 6 },
    },
    pipeline_by_stage: [
      {
        stage_id: '018f0000-0000-7000-8000-00000000s001',
        name: 'Contacto',
        amount: '30000.00',
        count: 4,
      },
      {
        stage_id: '018f0000-0000-7000-8000-00000000s002',
        name: 'Demo',
        amount: '22000.00',
        count: 2,
      },
    ],
    by_division: [
      {
        id: '018f0000-0000-7000-8000-00000000d001',
        name: 'Vascular',
        won_amount: '18000.00',
        won_count: 2,
        forecast_amount: '3000.00',
        open_amount: '40000.00',
        conversion_rate: 0.66,
      },
      {
        id: '018f0000-0000-7000-8000-00000000d002',
        name: 'FIV',
        won_amount: '12000.00',
        won_count: 1,
        forecast_amount: '1914.00',
        open_amount: '12000.00',
        conversion_rate: null,
      },
    ],
    by_rep: [
      {
        id: '018f0000-0000-7000-8000-00000000u001',
        name: 'Laura Vendedora',
        won_amount: '30000.00',
        won_count: 3,
        forecast_amount: '4914.00',
        open_amount: '52000.00',
        conversion_rate: 0.6,
      },
    ],
    activity: [
      {
        user_id: '018f0000-0000-7000-8000-00000000u001',
        name: 'Laura Vendedora',
        total: 5,
        by_type: [
          { code: 'visit', name: 'Visita', count: 3 },
          { code: 'call', name: 'Llamada', count: 2 },
        ],
      },
    ],
    neglected_accounts: {
      total: 2,
      items: [
        { id: NEGLECTED_ACCOUNT_ID, name: 'Clínica Tambre', days_since_contact: null },
        {
          id: '018f0000-0000-7000-8000-00000000a002',
          name: 'Hospital Sur',
          days_since_contact: 75,
        },
      ],
    },
  };
}

export const dashboardHandlers = [
  http.get(`${API_V1}/dashboard`, ({ request }) => {
    const url = new URL(request.url);
    const period = (url.searchParams.get('period') ?? 'month') as DashboardPeriod;
    return HttpResponse.json(dashboardPayload(period));
  }),
];
