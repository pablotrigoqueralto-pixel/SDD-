import { create } from 'zustand';

interface ConflictState {
  open: boolean;
  onReload: (() => Promise<void> | void) | null;
  show: (onReload: () => Promise<void> | void) => void;
  dismiss: () => void;
}

/** Global 409 handling: one dialog, opened by the query/mutation error handlers. */
export const useConflictStore = create<ConflictState>((set) => ({
  open: false,
  onReload: null,
  show: (onReload) => {
    set({ open: true, onReload });
  },
  dismiss: () => {
    set({ open: false, onReload: null });
  },
}));
