import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { accountKeys, contactKeys } from '@/api/query-keys';

import {
  anonymiseContact,
  createContact,
  getContact,
  listAccountContacts,
  listContacts,
  updateContact,
  type ContactCreate,
  type ContactListFilters,
  type ContactUpdate,
} from './api';

export function useAccountContacts(accountId: string | undefined, includeInactive = false) {
  return useQuery({
    queryKey: [...contactKeys.byAccount(accountId ?? ''), { includeInactive }],
    queryFn: () => listAccountContacts(accountId ?? '', includeInactive),
    enabled: Boolean(accountId),
  });
}

export const CONTACT_PAGE_SIZE = 25;

/** The global contacts list: one request per filter combination (desktop pagination). */
export function useContacts(filters: ContactListFilters) {
  return useQuery({
    queryKey: contactKeys.list({ ...filters }),
    queryFn: () => listContacts({ page_size: CONTACT_PAGE_SIZE, ...filters }),
    placeholderData: (previous) => previous,
  });
}

/** The same list on mobile, where the user loads more instead of paging. */
export function useInfiniteContacts(filters: Omit<ContactListFilters, 'page'>) {
  return useInfiniteQuery({
    queryKey: contactKeys.list({ ...filters, infinite: true }),
    queryFn: ({ pageParam }) =>
      listContacts({ page_size: CONTACT_PAGE_SIZE, ...filters, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page * lastPage.page_size < lastPage.total ? lastPage.page + 1 : undefined,
  });
}

export function useContact(id: string | undefined) {
  return useQuery({
    queryKey: contactKeys.detail(id ?? ''),
    queryFn: () => getContact(id ?? ''),
    enabled: Boolean(id),
  });
}

/** Contacts change what the account list shows (primary contact) and the 360º counters. */
function useInvalidateContacts() {
  const queryClient = useQueryClient();
  return async (accountId: string, contactId?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: contactKeys.byAccount(accountId) }),
      queryClient.invalidateQueries({ queryKey: accountKeys.detail(accountId) }),
      queryClient.invalidateQueries({ queryKey: accountKeys.lists() }),
      contactId
        ? queryClient.invalidateQueries({ queryKey: contactKeys.detail(contactId) })
        : Promise.resolve(),
    ]);
  };
}

interface CreateVariables {
  accountId: string;
  payload: ContactCreate;
}

export function useCreateContact() {
  const invalidate = useInvalidateContacts();
  return useMutation({
    mutationFn: ({ accountId, payload }: CreateVariables) => createContact(accountId, payload),
    onSuccess: (_data, { accountId }) => invalidate(accountId),
    meta: { silent: true },
  });
}

interface UpdateVariables {
  id: string;
  accountId: string;
  version: number;
  payload: ContactUpdate;
}

export function useUpdateContact() {
  const invalidate = useInvalidateContacts();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateVariables) => updateContact(id, version, payload),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}

interface AnonymiseVariables {
  id: string;
  accountId: string;
  version: number;
}

export function useAnonymiseContact() {
  const invalidate = useInvalidateContacts();
  return useMutation({
    mutationFn: ({ id, version }: AnonymiseVariables) => anonymiseContact(id, version),
    onSuccess: (_data, { accountId, id }) => invalidate(accountId, id),
    meta: { silent: true },
  });
}
