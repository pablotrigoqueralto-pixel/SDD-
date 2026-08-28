import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type OpportunityRead = components['schemas']['OpportunityRead'];
export type OpportunitySummaryRead = components['schemas']['OpportunitySummaryRead'];
export type OpportunityCreate = components['schemas']['OpportunityCreate'];
export type OpportunityUpdate = components['schemas']['OpportunityUpdate'];
export type OpportunityLineRead = components['schemas']['OpportunityLineRead'];
export type BoardRead = components['schemas']['BoardRead'];
export type BoardColumnRead = components['schemas']['BoardColumnRead'];
export type StageHistoryRead = components['schemas']['StageHistoryRead'];
export type OpportunityStatus = components['schemas']['OpportunityStatus'];

export interface OpportunityPage {
  items: OpportunitySummaryRead[];
  total: number;
  page: number;
  page_size: number;
}

export interface OpportunityListFilters {
  status?: 'open' | 'won' | 'lost' | 'all';
  pipeline_id?: string;
  stage_id?: string;
  division_id?: string;
  owner_id?: string;
  account_id?: string;
  is_tender?: boolean;
  is_at_risk?: boolean;
  close_from?: string;
  close_to?: string;
  q?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}

export interface BoardFilters {
  pipeline_id: string;
  division_id?: string;
  owner_id?: string;
}

function params(filters: object): Record<string, string | number | boolean> {
  const cleaned: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '' && value !== null) {
      cleaned[key] = value as string | number | boolean;
    }
  }
  return cleaned;
}

export async function listOpportunities(filters: OpportunityListFilters): Promise<OpportunityPage> {
  const { data } = await apiClient.get<OpportunityPage>('/opportunities', {
    params: params(filters),
  });
  return data;
}

export async function getBoard(filters: BoardFilters): Promise<BoardRead> {
  const { data } = await apiClient.get<BoardRead>('/opportunities/board', {
    params: params({ ...filters }),
  });
  return data;
}

export async function getOpportunity(id: string): Promise<OpportunityRead> {
  const { data } = await apiClient.get<OpportunityRead>(`/opportunities/${id}`);
  return data;
}

export async function listAccountOpportunities(
  accountId: string,
): Promise<OpportunitySummaryRead[]> {
  const { data } = await apiClient.get<OpportunitySummaryRead[]>(
    `/accounts/${accountId}/opportunities`,
  );
  return data;
}

export async function createOpportunity(payload: OpportunityCreate): Promise<OpportunityRead> {
  const { data } = await apiClient.post<OpportunityRead>('/opportunities', payload);
  return data;
}

export async function updateOpportunity(
  id: string,
  version: number,
  payload: OpportunityUpdate,
): Promise<OpportunityRead> {
  const { data } = await apiClient.patch<OpportunityRead>(`/opportunities/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function moveStage(
  id: string,
  version: number,
  stageId: string,
): Promise<OpportunityRead> {
  const { data } = await apiClient.post<OpportunityRead>(
    `/opportunities/${id}/stage`,
    { stage_id: stageId },
    { headers: ifMatch(version) },
  );
  return data;
}

export async function winOpportunity(
  id: string,
  version: number,
  payload: { won_amount?: string; won_at?: string },
): Promise<OpportunityRead> {
  const { data } = await apiClient.post<OpportunityRead>(`/opportunities/${id}/win`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function loseOpportunity(
  id: string,
  version: number,
  payload: { loss_reason_id: string; competitor_brand_id?: string; note?: string },
): Promise<OpportunityRead> {
  const { data } = await apiClient.post<OpportunityRead>(`/opportunities/${id}/lose`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function reopenOpportunity(
  id: string,
  version: number,
  stageId: string,
): Promise<OpportunityRead> {
  const { data } = await apiClient.post<OpportunityRead>(
    `/opportunities/${id}/reopen`,
    { stage_id: stageId },
    { headers: ifMatch(version) },
  );
  return data;
}

export async function setAtRisk(
  id: string,
  version: number,
  flag: boolean,
): Promise<OpportunityRead> {
  const { data } = await apiClient.post<OpportunityRead>(
    `/opportunities/${id}/at-risk`,
    { flag },
    { headers: ifMatch(version) },
  );
  return data;
}

export async function assignOpportunity(
  id: string,
  version: number,
  ownerId: string,
): Promise<OpportunityRead> {
  const { data } = await apiClient.put<OpportunityRead>(
    `/opportunities/${id}/assignment`,
    { owner_id: ownerId },
    { headers: ifMatch(version) },
  );
  return data;
}

export async function addLine(
  id: string,
  version: number,
  payload: { product_id: string; quantity: string; unit_price?: string },
): Promise<OpportunityRead> {
  const { data } = await apiClient.post<OpportunityRead>(`/opportunities/${id}/lines`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function updateLine(
  id: string,
  lineId: string,
  version: number,
  payload: { quantity?: string; unit_price?: string },
): Promise<OpportunityRead> {
  const { data } = await apiClient.patch<OpportunityRead>(
    `/opportunities/${id}/lines/${lineId}`,
    payload,
    { headers: ifMatch(version) },
  );
  return data;
}

export async function removeLine(id: string, lineId: string, version: number): Promise<void> {
  await apiClient.delete(`/opportunities/${id}/lines/${lineId}`, { headers: ifMatch(version) });
}
