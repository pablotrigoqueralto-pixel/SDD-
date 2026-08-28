import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';
import { useAccount } from '@/features/accounts';

import { ContactForm } from '../components/ContactForm';
import { useContact } from '../queries';

/** /centros/:id/contactos/nuevo and /centros/:id/contactos/:contactId/editar over the 360º page. */
export function ContactFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { accountId, contactId } = useParams<{ accountId: string; contactId?: string }>();
  const account = useAccount(accountId);
  const contact = useContact(contactId);
  const close = () => {
    navigate(routes.account(accountId ?? ''));
  };

  let body;
  if (account.isSuccess && (!contactId || contact.isSuccess)) {
    body = (
      <ContactForm
        key={contact.data?.version ?? 'new'}
        account={account.data}
        {...(contact.data ? { contact: contact.data } : {})}
        onSaved={close}
      />
    );
  } else if (account.isError || contact.isError) {
    const failed = account.isError ? account : contact;
    body = <ErrorState error={failed.error} onRetry={() => void failed.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer
      open
      title={contactId ? t('contacts:edit') : t('contacts:new')}
      onClose={close}
    >
      {body}
    </ResponsiveFormContainer>
  );
}
