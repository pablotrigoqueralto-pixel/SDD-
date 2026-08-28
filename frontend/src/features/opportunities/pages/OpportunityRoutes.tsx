import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';

import { LoseForm, WinForm } from '../components/CloseForms';
import { OpportunityForm } from '../components/OpportunityForm';
import { useOpportunity } from '../queries';

/** /oportunidades/nueva and /centros/:accountId/oportunidades/nueva. */
export function OpportunityNewRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { accountId } = useParams<{ accountId: string }>();
  return (
    <ResponsiveFormContainer
      open
      title={t('opportunities:new')}
      onClose={() => {
        navigate(-1);
      }}
    >
      <OpportunityForm
        {...(accountId ? { accountId } : {})}
        onSaved={(opportunity) => {
          navigate(routes.opportunity(opportunity.id), { replace: true });
        }}
      />
    </ResponsiveFormContainer>
  );
}

type DialogKind = 'edit' | 'win' | 'lose';

const TITLES: Record<DialogKind, string> = {
  edit: 'opportunities:edit',
  win: 'opportunities:win.title',
  lose: 'opportunities:lose.title',
};

/** /oportunidades/:id/editar | /ganar | /perder rendered over the sheet. */
export function OpportunityDialogRoute({ kind }: { kind: DialogKind }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { opportunityId } = useParams<{ opportunityId: string }>();
  const query = useOpportunity(opportunityId);
  const close = () => {
    navigate(routes.opportunity(opportunityId ?? ''));
  };

  let body;
  if (query.isSuccess) {
    const opportunity = query.data;
    if (kind === 'edit') {
      body = (
        <OpportunityForm key={opportunity.version} opportunity={opportunity} onSaved={close} />
      );
    } else if (kind === 'win') {
      body = <WinForm opportunity={opportunity} onSaved={close} />;
    } else {
      body = <LoseForm opportunity={opportunity} onSaved={close} />;
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
