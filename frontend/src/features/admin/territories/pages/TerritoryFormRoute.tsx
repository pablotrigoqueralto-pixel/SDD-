import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';

import { TerritoryForm } from '../components/TerritoryForm';
import { useTerritory } from '../queries';

export function TerritoryFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { territoryId } = useParams<{ territoryId: string }>();
  const territory = useTerritory(territoryId);
  const close = () => {
    navigate(routes.adminTerritories);
  };

  let body;
  if (!territoryId) {
    body = <TerritoryForm onSaved={close} />;
  } else if (territory.isSuccess) {
    body = (
      <TerritoryForm key={territory.data.version} territory={territory.data} onSaved={close} />
    );
  } else if (territory.isError) {
    body = <ErrorState error={territory.error} onRetry={() => void territory.refetch()} />;
  } else {
    body = <Skeleton className="h-64 w-full" />;
  }

  return (
    <ResponsiveFormContainer
      open
      title={territoryId ? t('admin:territories.edit') : t('admin:territories.new')}
      onClose={close}
    >
      {body}
    </ResponsiveFormContainer>
  );
}
