import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type LossReasonRead = components['schemas']['LossReasonRead'];
export type LossReasonCreate = components['schemas']['LossReasonCreate'];
export type LossReasonUpdate = components['schemas']['LossReasonUpdate'];

export async function listLossReasons(): Promise<LossReasonRead[]> {
  const { data } = await apiClient.get<LossReasonRead[]>('/loss-reasons');
  return data;
}

export async function createLossReason(payload: LossReasonCreate): Promise<LossReasonRead> {
  const { data } = await apiClient.post<LossReasonRead>('/loss-reasons', payload);
  return data;
}

export async function updateLossReason(
  id: string,
  version: number,
  payload: LossReasonUpdate,
): Promise<LossReasonRead> {
  const { data } = await apiClient.patch<LossReasonRead>(`/loss-reasons/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}
