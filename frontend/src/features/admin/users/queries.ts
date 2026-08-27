import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { userKeys } from '@/api/query-keys';

import type { UserCreate, UserUpdate } from '../types';
import { createUser, getUser, listUsers, updateUser, type UserListFilters } from './api';

export function useUsers(filters: UserListFilters) {
  return useQuery({
    queryKey: userKeys.list(filters as Record<string, unknown>),
    queryFn: () => listUsers(filters),
    placeholderData: (previous) => previous,
  });
}

export function useUser(id: string | undefined) {
  return useQuery({
    queryKey: userKeys.detail(id ?? ''),
    queryFn: () => getUser(id ?? ''),
    enabled: Boolean(id),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserCreate) => createUser(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
    meta: { silent: true },
  });
}

interface UpdateUserVariables {
  id: string;
  version: number;
  payload: UserUpdate;
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version, payload }: UpdateUserVariables) => updateUser(id, version, payload),
    onSuccess: async (user) => {
      queryClient.setQueryData(userKeys.detail(user.id), user);
      await queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
    meta: { silent: true },
  });
}
