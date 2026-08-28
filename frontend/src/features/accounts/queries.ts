import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { accountKeys } from '@/api/query-keys';

import {
  assignAccount,
  createAccount,
  getAccount,
  listAccounts,
  replaceAddresses,
  updateAccount,
  type AccountAssignment,
  type AccountCreate,
  type AccountListFilters,
  type AccountUpdate,
  type AddressWrite,
} from './api';

export const ACCOUNT_PAGE_SIZE = 25;

/** Paged list (desktop); `placeholderData` keeps the previous page while the next loads. */
export function useAccounts(filters: AccountListFilters) {
  return useQuery({
    queryKey: accountKeys.list(filters as Record<string, unknown>),
    queryFn: () => listAccounts({ page_size: ACCOUNT_PAGE_SIZE, ...filters }),
    placeholderData: (previous) => previous,
  });
}

/** "Cargar más" list (mobile): same filters, pages appended. */
export function useInfiniteAccounts(filters: Omit<AccountListFilters, 'page'>) {
  return useInfiniteQuery({
    queryKey: accountKeys.list({ ...filters, infinite: true }),
    queryFn: ({ pageParam }) =>
      listAccounts({ page_size: ACCOUNT_PAGE_SIZE, ...filters, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page * lastPage.page_size < lastPage.total ? lastPage.page + 1 : undefined,
  });
}

export function useAccount(id: string | undefined) {
  return useQuery({
    queryKey: accountKeys.detail(id ?? ''),
    queryFn: () => getAccount(id ?? ''),
    enabled: Boolean(id),
  });
}

function useInvalidateAccounts() {
  const queryClient = useQueryClient();
  return async (id?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: accountKeys.lists() }),
      id ? queryClient.invalidateQueries({ queryKey: accountKeys.detail(id) }) : Promise.resolve(),
    ]);
  };
}

export function useCreateAccount() {
  const invalidate = useInvalidateAccounts();
  return useMutation({
    mutationFn: (payload: AccountCreate) => createAccount(payload),
    onSuccess: () => invalidate(),
    meta: { silent: true },
  });
}

interface UpdateVariables {
  id: string;
  version: number;
  payload: AccountUpdate;
}

export function useUpdateAccount() {
  const invalidate = useInvalidateAccounts();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateVariables) => updateAccount(id, version, payload),
    onSuccess: (_data, { id }) => invalidate(id),
    meta: { silent: true },
  });
}

interface AssignVariables {
  id: string;
  version: number;
  payload: AccountAssignment;
}

export function useAssignAccount() {
  const invalidate = useInvalidateAccounts();
  return useMutation({
    mutationFn: ({ id, version, payload }: AssignVariables) => assignAccount(id, version, payload),
    onSuccess: (_data, { id }) => invalidate(id),
    meta: { silent: true },
  });
}

interface AddressesVariables {
  id: string;
  version: number;
  addresses: AddressWrite[];
}

export function useReplaceAddresses() {
  const invalidate = useInvalidateAccounts();
  return useMutation({
    mutationFn: ({ id, version, addresses }: AddressesVariables) =>
      replaceAddresses(id, version, addresses),
    onSuccess: (_data, { id }) => invalidate(id),
    meta: { silent: true },
  });
}
