import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { productKeys } from '@/api/query-keys';

import {
  createProduct,
  getProduct,
  listProducts,
  setProductActive,
  updateProduct,
  type ProductCreate,
  type ProductListFilters,
  type ProductUpdate,
} from './api';

export const PRODUCT_PAGE_SIZE = 25;

/** Paged list (desktop); `placeholderData` keeps the previous page while the next loads. */
export function useProducts(filters: ProductListFilters) {
  return useQuery({
    queryKey: productKeys.list(filters as Record<string, unknown>),
    queryFn: () => listProducts({ page_size: PRODUCT_PAGE_SIZE, ...filters }),
    placeholderData: (previous) => previous,
  });
}

/** "Cargar más" list (mobile): same filters, pages appended. */
export function useInfiniteProducts(filters: Omit<ProductListFilters, 'page'>) {
  return useInfiniteQuery({
    queryKey: productKeys.list({ ...filters, infinite: true }),
    queryFn: ({ pageParam }) =>
      listProducts({ page_size: PRODUCT_PAGE_SIZE, ...filters, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page * lastPage.page_size < lastPage.total ? lastPage.page + 1 : undefined,
  });
}

export function useProduct(id: string | undefined) {
  return useQuery({
    queryKey: productKeys.detail(id ?? ''),
    queryFn: () => getProduct(id ?? ''),
    enabled: Boolean(id),
  });
}

function useInvalidateProducts() {
  const queryClient = useQueryClient();
  return async (id?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: productKeys.lists() }),
      id ? queryClient.invalidateQueries({ queryKey: productKeys.detail(id) }) : Promise.resolve(),
    ]);
  };
}

export function useCreateProduct() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: (payload: ProductCreate) => createProduct(payload),
    onSuccess: () => invalidate(),
    meta: { silent: true },
  });
}

interface Versioned {
  id: string;
  version: number;
}

export function useUpdateProduct() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: ({ id, version, payload }: Versioned & { payload: ProductUpdate }) =>
      updateProduct(id, version, payload),
    onSuccess: (_data, { id }) => invalidate(id),
    meta: { silent: true },
  });
}

export function useSetProductActive() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: ({ id, version, active }: Versioned & { active: boolean }) =>
      setProductActive(id, version, active),
    onSuccess: (_data, { id }) => invalidate(id),
    meta: { silent: true },
  });
}
