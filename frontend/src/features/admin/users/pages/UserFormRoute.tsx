import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';

import { UserForm } from '../components/UserForm';
import { useUser } from '../queries';

/** /admin/usuarios/nuevo and /admin/usuarios/:id rendered over the list. */
export function UserFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { userId } = useParams<{ userId: string }>();
  const user = useUser(userId);
  const close = () => {
    navigate(routes.adminUsers);
  };

  let body;
  if (!userId) {
    body = <UserForm onSaved={close} />;
  } else if (user.isSuccess) {
    body = <UserForm key={user.data.version} user={user.data} onSaved={close} />;
  } else if (user.isError) {
    body = <ErrorState error={user.error} onRetry={() => void user.refetch()} />;
  } else {
    body = <Skeleton className="h-64 w-full" />;
  }

  return (
    <ResponsiveFormContainer
      open
      title={userId ? t('admin:users.edit') : t('admin:users.new')}
      onClose={close}
    >
      {body}
    </ResponsiveFormContainer>
  );
}
