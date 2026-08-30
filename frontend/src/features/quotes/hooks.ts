import { useSessionStore } from '@/features/auth';

import { fetchQuotePdf, type QuoteDetail, type QuoteSummaryRead } from './api';

export const QUOTE_MANAGER_ROLES = ['admin', 'sales_manager'] as const;

function isManager(role: string | undefined): boolean {
  return role !== undefined && (QUOTE_MANAGER_ROLES as readonly string[]).includes(role);
}

/** Drafts admit back office; the owner and management always write. */
export function useCanEditQuoteDraft(quote: QuoteDetail | QuoteSummaryRead | undefined): boolean {
  const user = useSessionStore((state) => state.user);
  if (!user || !quote) return false;
  if (isManager(user.role) || user.role === 'back_office') return true;
  return user.role === 'sales_rep' && quote.owner_id === user.id;
}

/** Send, accept, reject, revise and email retries: owner and management only. */
export function useCanRunQuoteLifecycle(
  quote: QuoteDetail | QuoteSummaryRead | undefined,
): boolean {
  const user = useSessionStore((state) => state.user);
  if (!user || !quote) return false;
  if (isManager(user.role)) return true;
  return user.role === 'sales_rep' && quote.owner_id === user.id;
}

export function useSeesQuoteCost(): boolean {
  const role = useSessionStore((state) => state.user?.role);
  return isManager(role);
}

/** Downloads the PDF with the JWT attached; plain links cannot carry the header. */
export async function downloadQuotePdf(quoteId: string, filename: string): Promise<void> {
  const blob = await fetchQuotePdf(quoteId);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
