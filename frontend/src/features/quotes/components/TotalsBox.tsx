import { useTranslation } from 'react-i18next';

import { formatPrice } from '@/features/catalogue';

interface TotalsBoxProps {
  totalBase: string;
  breakdown: { rate: string; vat: string }[];
  total: string;
  margin?: string | null;
}

function rateLabel(rate: string): string {
  return rate.replace(/\.00$/, '');
}

/** Base, VAT grouped by rate and the grand total, as printed on the PDF. */
export function TotalsBox({ totalBase, breakdown, total, margin }: TotalsBoxProps) {
  const { t } = useTranslation();
  return (
    <dl className="flex flex-col gap-1 rounded-lg border p-4 text-sm">
      <div className="flex items-center justify-between gap-4">
        <dt className="text-muted-foreground">{t('quotes:totals.base')}</dt>
        <dd className="tabular-nums">{formatPrice(totalBase)}</dd>
      </div>
      {breakdown.map((bucket) => (
        <div key={bucket.rate} className="flex items-center justify-between gap-4">
          <dt className="text-muted-foreground">
            {t('quotes:totals.vat', { rate: rateLabel(bucket.rate) })}
          </dt>
          <dd className="tabular-nums">{formatPrice(bucket.vat)}</dd>
        </div>
      ))}
      <div className="mt-1 flex items-center justify-between gap-4 border-t pt-2 font-semibold">
        <dt>{t('quotes:totals.total')}</dt>
        <dd className="tabular-nums">{formatPrice(total)}</dd>
      </div>
      {margin != null ? (
        <div className="flex items-center justify-between gap-4 text-muted-foreground">
          <dt>{t('quotes:totals.margin')}</dt>
          <dd className="tabular-nums">{formatPrice(margin)}</dd>
        </div>
      ) : null}
    </dl>
  );
}
