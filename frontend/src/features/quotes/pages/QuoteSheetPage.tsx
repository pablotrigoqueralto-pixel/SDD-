import { Download, Mail, Pencil, Send, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet, useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { formatPrice } from '@/features/catalogue';
import { toast } from '@/hooks/use-toast';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

import type { QuoteDetail } from '../api';
import { QuoteStatusBadge } from '../components/QuoteStatusBadge';
import { TotalsBox } from '../components/TotalsBox';
import {
  downloadQuotePdf,
  useCanEditQuoteDraft,
  useCanRunQuoteLifecycle,
  useSeesQuoteCost,
} from '../hooks';
import { useDeleteQuote, useQuote, useRetryQuoteEmail, useReviseQuote } from '../queries';

function formatDateTime(value: string | null | undefined, locale: string): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(value));
}

function LinesTable({ quote, showCost }: { quote: QuoteDetail; showCost: boolean }) {
  const { t } = useTranslation();
  return (
    <div
      role="region"
      aria-label={t('quotes:lines.title')}
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- axe requires scrollable regions to be keyboard reachable
      tabIndex={0}
      className="overflow-x-auto"
    >
      <table className="w-full min-w-[540px] text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2 pr-2 font-medium">{t('quotes:lines.description')}</th>
            <th className="py-2 pr-2 text-right font-medium">{t('quotes:lines.quantity')}</th>
            <th className="py-2 pr-2 text-right font-medium">{t('quotes:lines.unitPrice')}</th>
            <th className="py-2 pr-2 text-right font-medium">{t('quotes:lines.discount')}</th>
            <th className="py-2 pr-2 text-right font-medium">{t('quotes:lines.vat')}</th>
            {showCost ? (
              <th className="py-2 pr-2 text-right font-medium">{t('quotes:lines.cost')}</th>
            ) : null}
            <th className="py-2 text-right font-medium">{t('quotes:lines.base')}</th>
          </tr>
        </thead>
        <tbody>
          {quote.lines.map((line) => (
            <tr key={line.id} className="border-b last:border-0">
              <td className="py-2 pr-2">
                {line.description}
                {line.product_code ? (
                  <span className="block text-xs text-muted-foreground">{line.product_code}</span>
                ) : null}
              </td>
              <td className="py-2 pr-2 text-right tabular-nums">{line.quantity}</td>
              <td className="py-2 pr-2 text-right tabular-nums">{formatPrice(line.unit_price)}</td>
              <td className="py-2 pr-2 text-right tabular-nums">{line.discount_percent} %</td>
              <td className="py-2 pr-2 text-right tabular-nums">{line.vat_rate} %</td>
              {showCost ? (
                <td className="py-2 pr-2 text-right tabular-nums">
                  {'unit_cost' in line && line.unit_cost != null
                    ? formatPrice(line.unit_cost)
                    : '—'}
                </td>
              ) : null}
              <td className="py-2 text-right font-medium tabular-nums">{formatPrice(line.base)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The quote sheet: status, lines, totals, conditions, versions and lifecycle actions. */
export function QuoteSheetPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { quoteId } = useParams<{ quoteId: string }>();
  const query = useQuote(quoteId);
  const canEditDraft = useCanEditQuoteDraft(query.data);
  const canLifecycle = useCanRunQuoteLifecycle(query.data);
  const seesCost = useSeesQuoteCost();
  const deleteQuote = useDeleteQuote();
  const reviseQuote = useReviseQuote();
  const retryEmail = useRetryQuoteEmail();

  if (query.isPending) return <Skeleton className="mt-4 h-64 w-full" />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  const quote = query.data;
  const isDraft = quote.status === 'draft';
  const isSent = quote.status === 'sent';
  const isSuperseded = quote.superseded_at !== null;
  const currentVersion = quote.versions.find((version) => version.revision === quote.revision);
  const failure = (message: string) => {
    toast({ variant: 'destructive', description: message });
  };

  const handleDelete = async () => {
    if (!window.confirm(t('quotes:delete.confirm', { number: quote.display_number }))) return;
    try {
      await deleteQuote.mutateAsync({
        id: quote.id,
        accountId: quote.account_id,
        opportunityId: quote.opportunity_id,
      });
      toast({ description: t('quotes:deleted') });
      navigate(routes.quotes, { replace: true });
    } catch (error) {
      const problem = toProblem(error);
      failure(t(isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError'));
    }
  };

  const handleRevise = async () => {
    try {
      const revision = await reviseQuote.mutateAsync({
        id: quote.id,
        version: quote.version,
        accountId: quote.account_id,
        opportunityId: quote.opportunity_id,
      });
      toast({ description: t('quotes:revisedToast') });
      navigate(routes.quote(revision.id));
    } catch (error) {
      const problem = toProblem(error);
      failure(t(isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError'));
    }
  };

  const handleRetry = async () => {
    try {
      await retryEmail.mutateAsync({
        id: quote.id,
        accountId: quote.account_id,
        opportunityId: quote.opportunity_id,
      });
      toast({ description: t('quotes:sentToast') });
    } catch (error) {
      const problem = toProblem(error);
      failure(t(isKnownErrorCode(problem.code) ? `errors:${problem.code}` : 'toasts.genericError'));
    }
  };

  return (
    <>
      <PageHeader
        title={quote.display_number}
        backTo={routes.quotes}
        action={<QuoteStatusBadge quote={quote} />}
      />
      <section className="flex flex-col gap-4 py-4">
        {isSuperseded ? (
          <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
            {t('quotes:sheet.supersededNotice')}
          </p>
        ) : null}
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">{t('quotes:sheet.account')}</dt>
            <dd>
              <Link to={routes.account(quote.account_id)} className="underline">
                {quote.account_name}
              </Link>
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('quotes:sheet.opportunity')}</dt>
            <dd>
              <Link to={routes.opportunity(quote.opportunity_id)} className="underline">
                {quote.opportunity_name}
              </Link>
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('quotes:sheet.validUntil')}</dt>
            <dd>{quote.valid_until ? formatDateTime(quote.valid_until, i18n.language) : '—'}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('quotes:list.owner')}</dt>
            <dd>{quote.owner_name}</dd>
          </div>
          {quote.rejection_note ? (
            <div className="sm:col-span-2">
              <dt className="text-muted-foreground">{t('quotes:sheet.rejectionNote')}</dt>
              <dd>{quote.rejection_note}</dd>
            </div>
          ) : null}
        </dl>

        <LinesTable quote={quote} showCost={seesCost} />
        <TotalsBox
          totalBase={quote.total_base}
          breakdown={quote.vat_breakdown}
          total={quote.total}
          {...(seesCost && 'total_margin' in quote ? { margin: quote.total_margin } : {})}
        />

        <div>
          <h2 className="text-sm font-medium">{t('quotes:conditions.title')}</h2>
          <dl className="mt-1 grid gap-1 text-sm sm:grid-cols-2">
            <div className="flex gap-2">
              <dt className="text-muted-foreground">{t('quotes:conditions.validity')}:</dt>
              <dd>{quote.conditions.validez_dias}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">{t('quotes:conditions.delivery')}:</dt>
              <dd>{quote.conditions.plazo_entrega ?? '—'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">{t('quotes:conditions.payment')}:</dt>
              <dd>{quote.conditions.forma_pago ?? '—'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">{t('quotes:conditions.warranty')}:</dt>
              <dd>{quote.conditions.garantia ?? '—'}</dd>
            </div>
          </dl>
        </div>

        {quote.email_status ? (
          <div className="rounded-lg border p-3 text-sm">
            <h2 className="flex items-center gap-2 font-medium">
              <Mail className="size-4" aria-hidden="true" />
              {t('quotes:sheet.email.title')}
            </h2>
            <p className={quote.email_status === 'failed' ? 'text-destructive' : undefined}>
              {t(`quotes:sheet.email.${quote.email_status}`)}
              {quote.email_error ? ` — ${quote.email_error}` : ''}
            </p>
            {quote.email_status === 'failed' && canLifecycle ? (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 min-h-touch"
                disabled={retryEmail.isPending}
                onClick={() => void handleRetry()}
              >
                {t('quotes:sheet.email.retry')}
              </Button>
            ) : null}
          </div>
        ) : null}

        {quote.versions.length > 1 ? (
          <div>
            <h2 className="text-sm font-medium">{t('quotes:sheet.versions')}</h2>
            <ul className="mt-1 flex flex-wrap gap-2 text-sm">
              {quote.versions.map((version) => (
                <li key={version.id}>
                  {version.id === quote.id ? (
                    <span className="rounded-full border bg-muted px-3 py-1 font-medium">
                      {t('quotes:sheet.versionLabel', { revision: version.revision })}
                    </span>
                  ) : (
                    <Link
                      to={routes.quote(version.id)}
                      className="rounded-full border px-3 py-1 underline"
                    >
                      {t('quotes:sheet.versionLabel', { revision: version.revision })}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="min-h-touch"
            onClick={() => void downloadQuotePdf(quote.id, `${quote.display_number}.pdf`)}
          >
            <Download className="size-4" aria-hidden="true" />
            {t('quotes:actions.downloadPdf')}
          </Button>
          {isDraft && canEditDraft ? (
            <>
              <Button
                variant="outline"
                className="min-h-touch"
                onClick={() => {
                  navigate(routes.quoteEdit(quote.id));
                }}
              >
                <Pencil className="size-4" aria-hidden="true" />
                {t('quotes:actions.edit')}
              </Button>
              <Button
                variant="outline"
                className="min-h-touch"
                disabled={deleteQuote.isPending}
                onClick={() => void handleDelete()}
              >
                <Trash2 className="size-4" aria-hidden="true" />
                {t('quotes:actions.delete')}
              </Button>
            </>
          ) : null}
          {isDraft && canLifecycle ? (
            <Button
              className="min-h-touch"
              onClick={() => {
                navigate(routes.quoteSend(quote.id));
              }}
            >
              <Send className="size-4" aria-hidden="true" />
              {t('quotes:actions.send')}
            </Button>
          ) : null}
          {isSent && !isSuperseded && canLifecycle ? (
            <>
              <Button
                className="min-h-touch"
                onClick={() => {
                  navigate(routes.quoteAccept(quote.id));
                }}
              >
                {t('quotes:actions.accept')}
              </Button>
              <Button
                variant="destructive"
                className="min-h-touch"
                onClick={() => {
                  navigate(routes.quoteReject(quote.id));
                }}
              >
                {t('quotes:actions.reject')}
              </Button>
            </>
          ) : null}
          {(isSent || quote.status === 'rejected') && !isSuperseded && canLifecycle ? (
            <Button
              variant="outline"
              className="min-h-touch"
              disabled={reviseQuote.isPending}
              onClick={() => void handleRevise()}
            >
              {t('quotes:actions.revise')}
            </Button>
          ) : null}
        </div>
        {currentVersion ? null : null}
      </section>
      <Outlet />
    </>
  );
}
