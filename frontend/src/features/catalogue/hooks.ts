import { useSessionStore } from '@/features/auth';

export const CATALOGUE_WRITER_ROLES = ['admin', 'back_office'] as const;
export const COST_VIEWER_ROLES = ['admin', 'sales_manager'] as const;

/** Admin and back office maintain the catalogue. */
export function useCanEditCatalogue(): boolean {
  const role = useSessionStore((state) => state.user?.role);
  return role !== undefined && (CATALOGUE_WRITER_ROLES as readonly string[]).includes(role);
}

/** Cost is management information: sales managers and admins only. */
export function useCanViewCost(): boolean {
  const role = useSessionStore((state) => state.user?.role);
  return role !== undefined && (COST_VIEWER_ROLES as readonly string[]).includes(role);
}
