import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { accountKeys, activityKeys, opportunityKeys } from '@/api/query-keys';

import {
  addLine,
  assignOpportunity,
  createOpportunity,
  getBoard,
  getOpportunity,
  listAccountOpportunities,
  listOpportunities,
  loseOpportunity,
  moveStage,
  removeLine,
  reopenOpportunity,
  setAtRisk,
  updateLine,
  updateOpportunity,
  winOpportunity,
  type BoardFilters,
  type OpportunityCreate,
  type OpportunityListFilters,
  type OpportunityUpdate,
} from './api';

export const OPPORTUNITY_PAGE_SIZE = 25;

export function useOpportunities(filters: OpportunityListFilters) {
  return useQuery({
    queryKey: opportunityKeys.list(filters as Record<string, unknown>),
    queryFn: () => listOpportunities({ page_size: OPPORTUNITY_PAGE_SIZE, ...filters }),
    placeholderData: (previous) => previous,
  });
}

export function useBoard(filters: BoardFilters | null) {
  return useQuery({
    queryKey: opportunityKeys.board((filters ?? {}) as Record<string, unknown>),
    queryFn: () => getBoard(filters ?? { pipeline_id: '' }),
    enabled: filters !== null,
    placeholderData: (previous) => previous,
  });
}

export function useOpportunity(id: string | undefined) {
  return useQuery({
    queryKey: opportunityKeys.detail(id ?? ''),
    queryFn: () => getOpportunity(id ?? ''),
    enabled: Boolean(id),
  });
}

export function useAccountOpportunities(accountId: string | undefined) {
  return useQuery({
    queryKey: opportunityKeys.byAccount(accountId ?? ''),
    queryFn: () => listAccountOpportunities(accountId ?? ''),
    enabled: Boolean(accountId),
  });
}

/** Any opportunity change moves the lists, the board, the account section and "Hoy". */
function useInvalidateOpportunities() {
  const queryClient = useQueryClient();
  return async (accountId?: string, opportunityId?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: opportunityKeys.lists() }),
      queryClient.invalidateQueries({ queryKey: opportunityKeys.boards() }),
      queryClient.invalidateQueries({ queryKey: activityKeys.todays() }),
      accountId
        ? queryClient.invalidateQueries({ queryKey: opportunityKeys.byAccount(accountId) })
        : Promise.resolve(),
      accountId
        ? queryClient.invalidateQueries({ queryKey: accountKeys.detail(accountId) })
        : Promise.resolve(),
      accountId
        ? queryClient.invalidateQueries({ queryKey: activityKeys.timelines(accountId) })
        : Promise.resolve(),
      opportunityId
        ? queryClient.invalidateQueries({ queryKey: opportunityKeys.detail(opportunityId) })
        : Promise.resolve(),
    ]);
  };
}

export function useCreateOpportunity() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: (payload: OpportunityCreate) => createOpportunity(payload),
    onSuccess: (data) => invalidate(data.account_id, data.id),
    meta: { silent: true },
  });
}

interface Versioned {
  id: string;
  accountId: string;
  version: number;
}

export function useUpdateOpportunity() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({ id, version, payload }: Versioned & { payload: OpportunityUpdate }) =>
      updateOpportunity(id, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useMoveStage() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({ id, version, stageId }: Versioned & { stageId: string }) =>
      moveStage(id, version, stageId),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useWinOpportunity() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({
      id,
      version,
      payload,
    }: Versioned & { payload: { won_amount?: string; won_at?: string } }) =>
      winOpportunity(id, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useLoseOpportunity() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({
      id,
      version,
      payload,
    }: Versioned & {
      payload: { loss_reason_id: string; competitor_brand_id?: string; note?: string };
    }) => loseOpportunity(id, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useReopenOpportunity() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({ id, version, stageId }: Versioned & { stageId: string }) =>
      reopenOpportunity(id, version, stageId),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useSetAtRisk() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({ id, version, flag }: Versioned & { flag: boolean }) =>
      setAtRisk(id, version, flag),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useAssignOpportunity() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({ id, version, ownerId }: Versioned & { ownerId: string }) =>
      assignOpportunity(id, version, ownerId),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useAddLine() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({
      id,
      version,
      payload,
    }: Versioned & { payload: { product_id: string; quantity: string; unit_price?: string } }) =>
      addLine(id, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useUpdateLine() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({
      id,
      lineId,
      version,
      payload,
    }: Versioned & { lineId: string; payload: { quantity?: string; unit_price?: string } }) =>
      updateLine(id, lineId, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

export function useRemoveLine() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: ({ id, lineId, version }: Versioned & { lineId: string }) =>
      removeLine(id, lineId, version),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}
