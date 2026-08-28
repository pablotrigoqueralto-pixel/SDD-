import { useTerritories } from '@/features/admin';
import { useMe, useSessionStore } from '@/features/auth';

export const STAFF_ROLES = ['admin', 'sales_manager', 'back_office'] as const;

export function useIsStaff(): boolean {
  const role = useSessionStore((state) => state.user?.role);
  return role !== undefined && (STAFF_ROLES as readonly string[]).includes(role);
}

export function useIsManager(): boolean {
  const role = useSessionStore((state) => state.user?.role);
  return role === 'admin' || role === 'sales_manager';
}

export interface TerritoryOption {
  id: string;
  name: string;
  provinces: string[];
}

/** Territories the user can name: every territory for staff, the own ones for reps. */
export function useKnownTerritories(): TerritoryOption[] | undefined {
  const isStaff = useIsStaff();
  const all = useTerritories({ is_active: 'true' });
  const me = useMe(!isStaff);
  if (isStaff) return all.data?.items;
  return me.data?.territories;
}

export function territoryForProvince(
  territories: TerritoryOption[] | undefined,
  province: string,
): TerritoryOption | undefined {
  return territories?.find((territory) => territory.provinces.includes(province));
}
