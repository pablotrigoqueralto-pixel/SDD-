import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type PipelineRead = components['schemas']['PipelineRead'];
export type PipelineStageRead = components['schemas']['PipelineStageRead'];
export type StageUpdate = components['schemas']['StageUpdate'];

export async function listPipelines(): Promise<PipelineRead[]> {
  const { data } = await apiClient.get<PipelineRead[]>('/pipelines');
  return data;
}

export async function updateStage(
  pipelineId: string,
  stageId: string,
  version: number,
  payload: Pick<StageUpdate, 'name' | 'probability' | 'is_active'>,
): Promise<PipelineRead> {
  const { data } = await apiClient.patch<PipelineRead>(
    `/pipelines/${pipelineId}/stages/${stageId}`,
    payload,
    { headers: ifMatch(version) },
  );
  return data;
}

export async function reorderStages(
  pipelineId: string,
  version: number,
  stageIds: string[],
): Promise<PipelineRead> {
  const { data } = await apiClient.put<PipelineRead>(
    `/pipelines/${pipelineId}/stages/order`,
    { stage_ids: stageIds },
    { headers: ifMatch(version) },
  );
  return data;
}
