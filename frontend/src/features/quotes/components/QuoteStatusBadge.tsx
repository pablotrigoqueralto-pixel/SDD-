import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/badge';

import type { QuoteDetail, QuoteSummaryRead } from '../api';

interface QuoteStatusBadgeProps {
  quote: Pick<QuoteDetail | QuoteSummaryRead, 'status' | 'is_expired'>;
}

/** Estado badge; an expired sent quote shows Caducado instead of Enviado. */
export function QuoteStatusBadge({ quote }: QuoteStatusBadgeProps) {
  const { t } = useTranslation();
  if (quote.status === 'sent' && quote.is_expired) {
    return <Badge variant="destructive">{t('quotes:status.expired')}</Badge>;
  }
  const variant =
    quote.status === 'accepted'
      ? 'default'
      : quote.status === 'rejected'
        ? 'destructive'
        : quote.status === 'sent'
          ? 'secondary'
          : 'outline';
  return <Badge variant={variant}>{t(`quotes:status.${quote.status}`)}</Badge>;
}
