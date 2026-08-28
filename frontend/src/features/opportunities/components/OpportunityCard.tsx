import { useTranslation } from 'react-i18next';

import { formatWhen } from '@/features/activities';

import type { OpportunitySummaryRead } from '../api';
import { AmountText } from './AmountText';
import { StageBadge } from './StageBadge';

interface OpportunityCardProps {
  opportunity: OpportunitySummaryRead;
  onSelect?: (opportunity: OpportunitySummaryRead) => void;
  /** Compact body for board columns (no account line duplication controlled by caller). */
  showAccount?: boolean;
}

export function OpportunityCard({
  opportunity,
  onSelect,
  showAccount = true,
}: OpportunityCardProps) {
  const { t } = useTranslation();
  const body = (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="min-w-0 flex-1 truncate font-medium">{opportunity.name}</span>
        <AmountText amount={opportunity.amount} className="tabular-nums font-semibold" />
      </div>
      {showAccount ? (
        <p className="truncate text-sm text-muted-foreground">{opportunity.account_name}</p>
      ) : null}
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
        <StageBadge opportunity={opportunity} />
        <span>{t('opportunities:list.daysInStage', { count: opportunity.days_in_stage })}</span>
        <span>{formatWhen(opportunity.expected_close_date, 'date')}</span>
      </div>
    </>
  );
  if (onSelect) {
    return (
      <button
        type="button"
        onClick={() => {
          onSelect(opportunity);
        }}
        className="min-h-touch w-full rounded-lg border bg-card p-3 text-left active:bg-muted"
      >
        {body}
      </button>
    );
  }
  return <div className="rounded-lg border bg-card p-3">{body}</div>;
}
