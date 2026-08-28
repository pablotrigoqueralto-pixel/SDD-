import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';

import { AccountForm } from '../components/AccountForm';
import { AddressesForm } from '../components/AddressesForm';
import { AssignmentForm } from '../components/AssignmentForm';
import { useAccount } from '../queries';

/** /centros/nuevo rendered over the list; navigates to the 360º page once created. */
export function AccountCreateRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <ResponsiveFormContainer
      open
      title={t('accounts:new')}
      onClose={() => {
        navigate(routes.accounts);
      }}
    >
      <AccountForm
        onSaved={(account) => {
          navigate(routes.account(account.id), { replace: true });
        }}
      />
    </ResponsiveFormContainer>
  );
}

type Kind = 'edit' | 'addresses' | 'assign';

interface AccountDialogRouteProps {
  kind: Kind;
}

const TITLES: Record<Kind, string> = {
  edit: 'accounts:edit',
  addresses: 'accounts:addresses.title',
  assign: 'accounts:assignment.title',
};

/** /centros/:id/editar | /direcciones | /asignar rendered over the 360º page. */
export function AccountDialogRoute({ kind }: AccountDialogRouteProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { accountId } = useParams<{ accountId: string }>();
  const account = useAccount(accountId);
  const close = () => {
    navigate(routes.account(accountId ?? ''));
  };

  let body;
  if (account.isSuccess) {
    const data = account.data;
    if (kind === 'edit') {
      body = <AccountForm key={data.version} account={data} onSaved={close} />;
    } else if (kind === 'addresses') {
      body = <AddressesForm key={data.version} account={data} onSaved={close} />;
    } else {
      body = <AssignmentForm key={data.version} account={data} onSaved={close} />;
    }
  } else if (account.isError) {
    body = <ErrorState error={account.error} onRetry={() => void account.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer open title={t(TITLES[kind])} onClose={close}>
      {body}
    </ResponsiveFormContainer>
  );
}
