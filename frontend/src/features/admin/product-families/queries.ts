import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { referenceKeys } from '@/api/query-keys';

import {
  createProductFamily,
  listProductFamilies,
  updateProductFamily,
  type ProductFamilyCreate,
  type ProductFamilyUpdate,
} from './api';

export const productFamilyKeys = {
  all: ['product-families'] as const,
  list: () => [...productFamilyKeys.all, 'list'] as const,
};

export function useProductFamilyList() {
  return useQuery({ queryKey: productFamilyKeys.list(), queryFn: listProductFamilies });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: productFamilyKeys.all }),
      queryClient.invalidateQueries({ queryKey: referenceKeys.all }),
    ]);
  };
}

export function useCreateProductFamily() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: ProductFamilyCreate) => createProductFamily(payload),
    onSuccess: invalidate,
    meta: { silent: true },
  });
}

interface UpdateVariables {
  id: string;
  version: number;
  payload: ProductFamilyUpdate;
}

export function useUpdateProductFamily() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateVariables) =>
      updateProductFamily(id, version, payload),
    onSuccess: invalidate,
    meta: { silent: true },
  });
}
