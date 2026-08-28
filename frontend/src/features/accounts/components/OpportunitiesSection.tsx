import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { OpportunityCard, useAccountOpportunities } from '@/features/opportunities';

interface OpportunitiesSectionProps {
  accountId: string;
}

/** Open opportunities of the 360º page with the closed count and a create shortcut. */
export function OpportunitiesSection({ accountId }: OpportunitiesSectionProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const query = useAccountOpportunities(accountId);

  if (query.isPending) return <Skeleton className="h-16 w-full" />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  const open = query.data.filter((item) => item.status === 'open');
  const closed = query.data.length - open.length;
  const newButton = (
    <Button
      variant="outline"
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.accountOpportunityNew(accountId));
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('opportunities:new')}
    </Button>
  );
  return (
    <div className="flex flex-col gap-2">
      {open.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('opportunities:account.empty')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {open.map((opportunity) => (
            <li key={opportunity.id}>
              <OpportunityCard
                opportunity={opportunity}
                showAccount={false}
                onSelect={(selected) => {
                  navigate(routes.opportunity(selected.id));
                }}
              />
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-muted-foreground">
          {closed > 0 ? t('opportunities:account.closed', { count: closed }) : null}
          {closed > 0 ? ' · ' : null}
          <Link
            to={`${routes.opportunities}?account_id=${encodeURIComponent(accountId)}&status=all`}
            className="underline"
          >
            {t('opportunities:account.seeAll')}
          </Link>
        </span>
        {newButton}
      </div>
    </div>
  );
}
