import { create } from 'zustand';

import type { components } from '@/api/schema';

export type SessionUser = components['schemas']['UserRead'];
export type SessionStatus = 'unknown' | 'authenticated' | 'anonymous';

interface SessionState {
  status: SessionStatus;
  accessToken: string | null;
  user: SessionUser | null;
  setSession: (accessToken: string, user: SessionUser) => void;
  setUser: (user: SessionUser) => void;
  clear: () => void;
}

/** Access token lives in memory only; the refresh cookie survives reloads. */
export const useSessionStore = create<SessionState>((set) => ({
  status: 'unknown',
  accessToken: null,
  user: null,
  setSession: (accessToken, user) => {
    set({ status: 'authenticated', accessToken, user });
  },
  setUser: (user) => {
    set({ user });
  },
  clear: () => {
    set({ status: 'anonymous', accessToken: null, user: null });
  },
}));

export const sessionStore = useSessionStore;
