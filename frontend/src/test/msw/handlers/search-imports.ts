import { http, HttpResponse } from 'msw';

import type { components } from '@/api/schema';

import { TAMBRE_ID } from '../accounts-fixtures';
import { API_V1 } from '../constants';
import { OPP_ID } from '../opportunities-fixtures';
import { QUOTE_SENT_ID } from '../quotes-fixtures';

type SearchResultsRead = components['schemas']['SearchResultsRead'];
type ImportReportRead = components['schemas']['ImportReportRead'];

export function searchResults(q: string): SearchResultsRead {
  return {
    q,
    accounts: {
      items: [
        {
          id: TAMBRE_ID,
          name: 'Clínica Tambre',
          city: 'Madrid',
          province_code: '28',
          is_active: true,
        },
      ],
      total: 7,
      has_more: true,
    },
    contacts: {
      items: [
        {
          id: 'contact-ana',
          account_id: TAMBRE_ID,
          account_name: 'Clínica Tambre',
          full_name: 'Ana Pérez',
          email: 'ana@tambre.es',
          mobile: '+34612345678',
        },
      ],
      total: 1,
      has_more: false,
    },
    opportunities: {
      items: [
        {
          id: OPP_ID,
          account_id: TAMBRE_ID,
          account_name: 'Clínica Tambre',
          name: 'Clínica Tambre · Vascular · agosto 2026',
          stage_name: 'Demo',
          status: 'open',
          amount: '30000.00',
          is_tender: false,
        },
      ],
      total: 1,
      has_more: false,
    },
    quotes: {
      items: [
        {
          id: QUOTE_SENT_ID,
          opportunity_id: OPP_ID,
          account_name: 'Clínica Tambre',
          display_number: 'P-2026-0002',
          status: 'sent',
          is_expired: false,
          total: '31460.00',
          valid_until: '2026-09-26',
        },
      ],
      total: 1,
      has_more: false,
    },
  };
}

export const emptySearchResults = (q: string): SearchResultsRead => ({
  q,
  accounts: { items: [], total: 0, has_more: false },
  contacts: { items: [], total: 0, has_more: false },
  opportunities: { items: [], total: 0, has_more: false },
  quotes: { items: [], total: 0, has_more: false },
});

export const importPreviewReport: ImportReportRead = {
  dry_run: true,
  created: 2,
  updated: 1,
  unchanged: 3,
  errors: 1,
  rows: [
    { row: 2, outcome: 'created', label: 'IMP-1', message: null },
    { row: 3, outcome: 'created', label: 'IMP-2', message: null },
    { row: 4, outcome: 'updated', label: 'IMP-3', message: null },
    { row: 5, outcome: 'unchanged', label: 'IMP-4', message: null },
    { row: 6, outcome: 'unchanged', label: 'IMP-5', message: null },
    { row: 7, outcome: 'unchanged', label: 'IMP-6', message: null },
    { row: 8, outcome: 'error', label: 'IMP-7', message: 'Unknown brand: Desconocida' },
  ],
};

export const importAppliedReport: ImportReportRead = {
  ...importPreviewReport,
  dry_run: false,
};

/** Stateless defaults; tests override with server.use(). */
export const searchImportHandlers = [
  http.get(`${API_V1}/search`, ({ request }) => {
    const q = new URL(request.url).searchParams.get('q') ?? '';
    if (q.trim().length < 2) return HttpResponse.json(emptySearchResults(q));
    return HttpResponse.json(searchResults(q));
  }),
  http.post(`${API_V1}/products/import`, ({ request }) => {
    const dryRun = new URL(request.url).searchParams.get('dry_run') !== 'false';
    return HttpResponse.json(dryRun ? importPreviewReport : importAppliedReport);
  }),
  http.post(`${API_V1}/accounts/import`, ({ request }) => {
    const dryRun = new URL(request.url).searchParams.get('dry_run') !== 'false';
    return HttpResponse.json(dryRun ? importPreviewReport : importAppliedReport);
  }),
];
