import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { referenceKeys } from '@/api/query-keys';

import {
  createLossReason,
  listLossReasons,
  updateLossReason,
  type LossReasonCreate,
  type LossReasonUpdate,
} from './api';

export const lossReasonKeys = {
  all: ['loss-reasons'] as const,
  list: () => [...lossReasonKeys.all, 'list'] as const,
};

export function useLossReasonList() {
  return useQuery({ queryKey: lossReasonKeys.list(), queryFn: listLossReasons });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: lossReasonKeys.all }),
      queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
    ]);
  };
}

export function useCreateLossReason() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: LossReasonCreate) => createLossReason(payload),
    onSuccess: invalidate,
    meta: { silent: true },
  });
}

interface UpdateVariables {
  id: string;
  version: number;
  payload: LossReasonUpdate;
}

export function useUpdateLossReason() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateVariables) =>
      updateLossReason(id, version, payload),
    onSuccess: invalidate,
    meta: { silent: true },
  });
}
