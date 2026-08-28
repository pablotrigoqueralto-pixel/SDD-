import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Skeleton } from '@/components/ui/skeleton';

import { ProductForm } from '../components/ProductForm';
import { useCanEditCatalogue } from '../hooks';
import { useProduct } from '../queries';

/** /catalogo/nuevo and /catalogo/:productId rendered over the list (read-only without rights). */
export function ProductFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const canEdit = useCanEditCatalogue();
  const { productId } = useParams<{ productId: string }>();
  const product = useProduct(productId);
  const close = () => {
    navigate(routes.catalogue);
  };

  let body;
  let title = t('catalogue:new');
  if (!productId) {
    body = <ProductForm onSaved={close} />;
  } else if (product.isSuccess) {
    title = canEdit ? t('catalogue:edit') : t('catalogue:view');
    body = <ProductForm key={product.data.version} product={product.data} onSaved={close} />;
  } else if (product.isError) {
    title = t('catalogue:product');
    body = <ErrorState error={product.error} onRetry={() => void product.refetch()} />;
  } else {
    title = t('catalogue:product');
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer open title={title} onClose={close}>
      {body}
    </ResponsiveFormContainer>
  );
}
