import { useTranslation } from 'react-i18next';
import { Route, Routes, useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';

import { AcceptQuoteDialog, RejectQuoteDialog } from './components/CloseQuoteDialogs';
import { QuoteForm } from './components/QuoteForm';
import { SendQuoteDialog } from './components/SendQuoteDialog';
import { QuoteSheetPage } from './pages/QuoteSheetPage';
import { QuotesListPage } from './pages/QuotesListPage';
import { useQuote } from './queries';

type DialogKind = 'edit' | 'send' | 'accept' | 'reject';

const TITLES: Record<DialogKind, string> = {
  edit: 'quotes:edit',
  send: 'quotes:send.title',
  accept: 'quotes:accept.title',
  reject: 'quotes:reject.title',
};

/** /presupuestos/:id/editar | /enviar | /aceptar | /rechazar rendered over the sheet. */
function QuoteDialogRoute({ kind }: { kind: DialogKind }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { quoteId } = useParams<{ quoteId: string }>();
  const query = useQuote(quoteId);
  const close = () => {
    navigate(routes.quote(quoteId ?? ''));
  };

  let body;
  if (query.isSuccess) {
    const quote = query.data;
    if (kind === 'edit') {
      body = <QuoteForm key={quote.version} quote={quote} onSaved={close} />;
    } else if (kind === 'send') {
      body = <SendQuoteDialog quote={quote} onSent={close} />;
    } else if (kind === 'accept') {
      body = <AcceptQuoteDialog quote={quote} onDone={close} />;
    } else {
      body = <RejectQuoteDialog quote={quote} onDone={close} />;
    }
  } else if (query.isError) {
    body = <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer open title={t(TITLES[kind])} onClose={close}>
      {body}
    </ResponsiveFormContainer>
  );
}

/** Mounted under /presupuestos/* for every authenticated role. */
export function QuoteRoutes() {
  return (
    <Routes>
      <Route path="/" element={<QuotesListPage />} />
      <Route path=":quoteId" element={<QuoteSheetPage />}>
        <Route path="editar" element={<QuoteDialogRoute kind="edit" />} />
        <Route path="enviar" element={<QuoteDialogRoute kind="send" />} />
        <Route path="aceptar" element={<QuoteDialogRoute kind="accept" />} />
        <Route path="rechazar" element={<QuoteDialogRoute kind="reject" />} />
      </Route>
    </Routes>
  );
}
