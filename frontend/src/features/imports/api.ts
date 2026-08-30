import { apiClient } from '@/api/client';
import type { components } from '@/api/schema';

export type ImportReportRead = components['schemas']['ImportReportRead'];
export type ImportRowRead = components['schemas']['ImportRowRead'];
export type ImportTarget = 'products' | 'accounts';

const ENDPOINTS: Record<ImportTarget, string> = {
  products: '/products/import',
  accounts: '/accounts/import',
};

export async function runImport(
  target: ImportTarget,
  file: File,
  dryRun: boolean,
): Promise<ImportReportRead> {
  const body = new FormData();
  body.append('file', file);
  const { data } = await apiClient.post<ImportReportRead>(ENDPOINTS[target], body, {
    params: { dry_run: dryRun },
  });
  return data;
}

/** Client-side error report: the failing rows as a downloadable CSV. */
export function errorReportCsv(report: ImportReportRead): string {
  const lines = ['fila;registro;error'];
  for (const row of report.rows) {
    if (row.outcome !== 'error') continue;
    const message = (row.message ?? '').replaceAll(';', ',').replaceAll('\n', ' ');
    lines.push(`${String(row.row)};${row.label.replaceAll(';', ',')};${message}`);
  }
  return lines.join('\n');
}
