import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';

import { BrandForm } from '../components/BrandForm';
import { useBrandList } from '../queries';

/** /admin/marcas/nueva and /admin/marcas/:id rendered over the list. */
export function BrandFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { brandId } = useParams<{ brandId: string }>();
  const brands = useBrandList({});
  const brand = brands.data?.find((candidate) => candidate.id === brandId);
  const close = () => {
    navigate(routes.adminBrands);
  };

  let body;
  if (!brandId) {
    body = <BrandForm onSaved={close} />;
  } else if (brands.isSuccess && brand) {
    body = <BrandForm key={brand.version} brand={brand} onSaved={close} />;
  } else if (brands.isError || (brands.isSuccess && !brand)) {
    body = <ErrorState error={brands.error} onRetry={() => void brands.refetch()} />;
  } else {
    body = <Skeleton className="h-64 w-full" />;
  }

  return (
    <ResponsiveFormContainer
      open
      title={brandId ? t('admin:brands.edit') : t('admin:brands.new')}
      onClose={close}
    >
      {body}
    </ResponsiveFormContainer>
  );
}
