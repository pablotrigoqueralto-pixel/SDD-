import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { referenceKeys } from '@/api/query-keys';

import {
  createBrand,
  listBrands,
  updateBrand,
  type BrandCreate,
  type BrandFilters,
  type BrandUpdate,
} from './api';

export const brandKeys = {
  all: ['brands'] as const,
  list: (filters: BrandFilters) => [...brandKeys.all, 'list', filters] as const,
};

export function useBrandList(filters: BrandFilters) {
  return useQuery({
    queryKey: brandKeys.list(filters),
    queryFn: () => listBrands(filters),
    placeholderData: (previous) => previous,
  });
}

export function useCreateBrand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BrandCreate) => createBrand(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: brandKeys.all }),
        queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
      ]);
    },
    meta: { silent: true },
  });
}

interface UpdateBrandVariables {
  id: string;
  version: number;
  payload: BrandUpdate;
}

export function useUpdateBrand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateBrandVariables) =>
      updateBrand(id, version, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: brandKeys.all }),
        queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
      ]);
    },
    meta: { silent: true },
  });
}
