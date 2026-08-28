import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/badge';

import type { OpportunityRead, OpportunitySummaryRead } from '../api';

interface StageBadgeProps {
  opportunity: OpportunityRead | OpportunitySummaryRead;
}

/** Stage name plus the state badges every list and card shows. */
export function StageBadge({ opportunity }: StageBadgeProps) {
  const { t } = useTranslation();
  const variant =
    opportunity.status === 'won'
      ? 'default'
      : opportunity.status === 'lost'
        ? 'destructive'
        : 'secondary';
  return (
    <span className="flex flex-wrap items-center gap-1">
      <Badge variant={variant}>{opportunity.stage_name}</Badge>
      {opportunity.is_tender ? (
        <Badge variant="outline">{t('opportunities:badges.tender')}</Badge>
      ) : null}
      {opportunity.is_at_risk ? (
        <Badge variant="destructive">{t('opportunities:badges.atRisk')}</Badge>
      ) : null}
    </span>
  );
}
