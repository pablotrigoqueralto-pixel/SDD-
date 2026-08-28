import { AlertTriangle, Gavel } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import type { components } from '@/api/schema';
import { routes } from '@/app/routes';

import { formatWhen } from './ActivityCard';

type OpportunitySummaryRead = components['schemas']['OpportunitySummaryRead'];

interface OpportunityBlocksProps {
  tenders: OpportunitySummaryRead[];
  atRisk: OpportunitySummaryRead[];
}

/** "Licitaciones esta semana" and "Centros en riesgo" on the Hoy page (hidden when empty). */
export function OpportunityBlocks({ tenders, atRisk }: OpportunityBlocksProps) {
  const { t } = useTranslation();
  const today = new Date().toISOString().slice(0, 10);
  if (tenders.length === 0 && atRisk.length === 0) return null;
  return (
    <>
      {tenders.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <Gavel className="size-4" aria-hidden="true" />
            {t('opportunities:today.tenders')}
          </h2>
          <ul className="flex flex-col gap-2">
            {tenders.map((opportunity) => {
              const overdue =
                opportunity.tender_deadline !== null && opportunity.tender_deadline < today;
              return (
                <li key={opportunity.id}>
                  <Link
                    to={routes.opportunity(opportunity.id)}
                    className={`block rounded-lg border p-3 text-sm ${
                      overdue ? 'border-destructive/60 bg-destructive/10' : 'bg-card'
                    }`}
                  >
                    <span className="font-medium">{opportunity.name}</span>
                    <span className="block text-muted-foreground">
                      {opportunity.account_name}
                      {opportunity.tender_deadline
                        ? ` · ${t('opportunities:today.tenderDue', {
                            date: formatWhen(opportunity.tender_deadline, 'date'),
                          })}`
                        : ''}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
      {atRisk.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <AlertTriangle className="size-4" aria-hidden="true" />
            {t('opportunities:today.atRisk')}
          </h2>
          <ul className="flex flex-col gap-2">
            {atRisk.map((opportunity) => (
              <li key={opportunity.id}>
                <Link
                  to={routes.opportunity(opportunity.id)}
                  className="block rounded-lg border bg-card p-3 text-sm"
                >
                  <span className="font-medium">{opportunity.account_name}</span>
                  <span className="block text-muted-foreground">{opportunity.name}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
