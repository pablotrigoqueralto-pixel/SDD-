import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { authKeys } from '@/api/query-keys';
import { useSessionStore } from '@/store/session.store';

import { changePassword, getMe, login, logout, type LoginRequest } from './api';

export function useLogin() {
  const setSession = useSessionStore((state) => state.setSession);
  return useMutation({
    mutationFn: (payload: LoginRequest) => login(payload),
    onSuccess: (data) => {
      setSession(data.access_token, data.user);
    },
    meta: { silent: true },
  });
}

export function useLogout() {
  const clear = useSessionStore((state) => state.clear);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      clear();
      queryClient.clear();
    },
    meta: { silent: true },
  });
}

export function useMe(enabled = true) {
  return useQuery({ queryKey: authKeys.me(), queryFn: getMe, enabled, staleTime: 5 * 60_000 });
}

export function useChangePassword() {
  return useMutation({ mutationFn: changePassword, meta: { silent: true } });
}
