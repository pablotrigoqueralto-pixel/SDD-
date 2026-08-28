import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { territoryKeys } from '@/api/query-keys';

import type { TerritoryCreate, TerritoryUpdate } from '../types';
import {
  createTerritory,
  getTerritory,
  listTerritories,
  updateTerritory,
  type TerritoryListFilters,
} from './api';

const REFERENCE_STALE_TIME = 5 * 60_000;

export function useTerritories(filters: TerritoryListFilters = {}) {
  return useQuery({
    queryKey: territoryKeys.list(filters as Record<string, unknown>),
    queryFn: () => listTerritories(filters),
    staleTime: REFERENCE_STALE_TIME,
    placeholderData: (previous) => previous,
  });
}

export function useTerritory(id: string | undefined) {
  return useQuery({
    queryKey: territoryKeys.detail(id ?? ''),
    queryFn: () => getTerritory(id ?? ''),
    enabled: Boolean(id),
  });
}

export function useCreateTerritory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TerritoryCreate) => createTerritory(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: territoryKeys.all });
    },
    meta: { silent: true },
  });
}

interface UpdateTerritoryVariables {
  id: string;
  version: number;
  payload: TerritoryUpdate;
}

export function useUpdateTerritory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateTerritoryVariables) =>
      updateTerritory(id, version, payload),
    onSuccess: async (territory) => {
      queryClient.setQueryData(territoryKeys.detail(territory.id), territory);
      await queryClient.invalidateQueries({ queryKey: territoryKeys.lists() });
    },
    meta: { silent: true },
  });
}
