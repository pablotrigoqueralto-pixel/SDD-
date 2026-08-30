import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { formatPrice } from '@/features/catalogue';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { QuoteSummaryRead } from '../api';
import { useCreateQuote, useOpportunityQuotes, useQuotes } from '../queries';
import { QuoteStatusBadge } from './QuoteStatusBadge';

function QuoteRow({ quote, onSelect }: { quote: QuoteSummaryRead; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="flex min-h-touch w-full flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-left text-sm hover:bg-muted"
    >
      <span className="font-medium">{quote.display_number}</span>
      <QuoteStatusBadge quote={quote} />
      <span className="tabular-nums">{formatPrice(quote.total)}</span>
    </button>
  );
}

interface QuotesSectionProps {
  /** Opportunity sheet variant: lists the opportunity's quotes and can create. */
  opportunityId?: string;
  /** Account 360º variant: lists every current version of the account. */
  accountId?: string;
  /** Creation only on open opportunities for lifecycle-capable roles. */
  canCreate?: boolean;
}

export function QuotesSection({ opportunityId, accountId, canCreate = false }: QuotesSectionProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const createQuote = useCreateQuote();
  const byOpportunity = useOpportunityQuotes(opportunityId);
  const byAccount = useQuotes(accountId ? { account_id: accountId, status: 'all' } : {});
  const query = opportunityId ? byOpportunity : byAccount;
  const items: QuoteSummaryRead[] = opportunityId
    ? (byOpportunity.data ?? [])
    : (byAccount.data?.items ?? []);

  const handleCreate = async () => {
    if (!opportunityId) return;
    try {
      const quote = await createQuote.mutateAsync({ opportunity_id: opportunityId });
      toast({ description: t('quotes:created') });
      navigate(routes.quote(quote.id));
    } catch (error) {
      const problem = toProblem(error);
      toast({
        variant: 'destructive',
        description: t(
          isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError',
        ),
      });
    }
  };

  if (query.isPending) return <Skeleton className="h-16 w-full" />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  return (
    <div className="flex flex-col gap-2">
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('quotes:section.empty')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((quote) => (
            <li key={quote.id}>
              <QuoteRow
                quote={quote}
                onSelect={() => {
                  navigate(routes.quote(quote.id));
                }}
              />
            </li>
          ))}
        </ul>
      )}
      {opportunityId && canCreate ? (
        <Button
          variant="outline"
          size="sm"
          className="min-h-touch self-start"
          disabled={createQuote.isPending}
          onClick={() => void handleCreate()}
        >
          <Plus className="size-4" aria-hidden="true" />
          {t('quotes:new')}
        </Button>
      ) : null}
    </div>
  );
}
