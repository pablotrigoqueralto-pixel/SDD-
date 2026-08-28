import { useSessionStore } from '@/features/auth';

import type { OpportunityRead, OpportunitySummaryRead } from './api';

export const OPPORTUNITY_MANAGER_ROLES = ['admin', 'sales_manager'] as const;

export function useIsOpportunityManager(): boolean {
  const role = useSessionStore((state) => state.user?.role);
  return role !== undefined && (OPPORTUNITY_MANAGER_ROLES as readonly string[]).includes(role);
}

/** The owner and sales management write; back office and other reps read. */
export function useCanWriteOpportunity(
  opportunity: OpportunityRead | OpportunitySummaryRead | undefined,
): boolean {
  const user = useSessionStore((state) => state.user);
  if (!user || !opportunity) return false;
  if ((OPPORTUNITY_MANAGER_ROLES as readonly string[]).includes(user.role)) return true;
  return user.role === 'sales_rep' && opportunity.owner_id === user.id;
}
