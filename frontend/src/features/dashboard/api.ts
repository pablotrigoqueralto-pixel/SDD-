import { apiClient } from '@/api/client';
import type { components } from '@/api/schema';

export type DashboardRead = components['schemas']['DashboardRead'];
export type DashboardPeriod = components['schemas']['DashboardPeriod'];
export type SummaryRead = components['schemas']['SummaryRead'];
export type StageRowRead = components['schemas']['StageRowRead'];
export type BreakdownRowRead = components['schemas']['BreakdownRowRead'];
export type ActivityRowRead = components['schemas']['ActivityRowRead'];
export type NeglectedAccountsRead = components['schemas']['NeglectedAccountsRead'];

export async function fetchDashboard(period: DashboardPeriod): Promise<DashboardRead> {
  const { data } = await apiClient.get<DashboardRead>('/dashboard', { params: { period } });
  return data;
}
