import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { referenceKeys } from '@/api/query-keys';

import { listPipelines, reorderStages, updateStage, type StageUpdate } from './api';

export const pipelineKeys = {
  all: ['pipelines'] as const,
  list: () => [...pipelineKeys.all, 'list'] as const,
};

export function usePipelineList() {
  return useQuery({ queryKey: pipelineKeys.list(), queryFn: listPipelines });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: pipelineKeys.all }),
      queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
    ]);
  };
}

interface UpdateStageVariables {
  pipelineId: string;
  stageId: string;
  version: number;
  payload: Pick<StageUpdate, 'name' | 'probability' | 'is_active'>;
}

export function useUpdateStage() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ pipelineId, stageId, version, payload }: UpdateStageVariables) =>
      updateStage(pipelineId, stageId, version, payload),
    onSuccess: invalidate,
    meta: { silent: true },
  });
}

interface ReorderVariables {
  pipelineId: string;
  version: number;
  stageIds: string[];
}

export function useReorderStages() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ pipelineId, version, stageIds }: ReorderVariables) =>
      reorderStages(pipelineId, version, stageIds),
    onSuccess: invalidate,
    meta: { conflictKeys: [pipelineKeys.all, referenceKeys.all] },
  });
}
