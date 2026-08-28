import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useDivisions } from '@/features/reference';

import type { ProductFamilyRead } from '../api';
import { ProductFamilyForm } from '../components/ProductFamilyForm';
import { useProductFamilyList } from '../queries';

export function ProductFamilyListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const families = useProductFamilyList();
  const divisions = useDivisions();

  const columns: DataListColumn<ProductFamilyRead>[] = [
    {
      key: 'name',
      header: t('admin:productFamilies.form.name'),
      cell: (family) => family.name_es,
    },
    {
      key: 'order',
      header: t('admin:productFamilies.form.sortOrder'),
      cell: (family) => String(family.sort_order),
    },
    {
      key: 'state',
      header: t('admin:users.filterActive'),
      cell: (family) =>
        family.is_active ? null : <Badge variant="outline">{t('status.inactive')}</Badge>,
    },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.adminProductFamilyNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('admin:productFamilies.new')}
    </Button>
  );

  const groups = (divisions.data ?? [])
    .map((division) => ({
      division,
      items: (families.data ?? []).filter((family) => family.division_id === division.id),
    }))
    .filter((group) => group.items.length > 0);

  let body;
  if (families.isPending || divisions.isPending) {
    body = <Skeleton className="h-40 w-full" />;
  } else if (families.isError) {
    body = <ErrorState error={families.error} onRetry={() => void families.refetch()} />;
  } else if (groups.length === 0) {
    body = <EmptyState title={t('admin:productFamilies.empty')} action={newButton} />;
  } else {
    body = groups.map((group) => (
      <section key={group.division.id} className="flex flex-col gap-2">
        <h2 className="text-base font-semibold">{group.division.name_es}</h2>
        <DataList
          items={group.items}
          columns={columns}
          getKey={(family) => family.id}
          onSelect={(family) => {
            navigate(routes.adminProductFamily(family.id));
          }}
          isLoading={false}
          emptyTitle={t('admin:productFamilies.empty')}
        />
      </section>
    ));
  }

  return (
    <>
      <PageHeader
        title={t('admin:productFamilies.title')}
        backTo={routes.admin}
        action={newButton}
      />
      <div className="flex flex-col gap-6 py-3">{body}</div>
      <Outlet />
    </>
  );
}

/** /admin/familias/nueva and /admin/familias/:id rendered over the list. */
export function ProductFamilyFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { familyId } = useParams<{ familyId: string }>();
  const families = useProductFamilyList();
  const family = families.data?.find((candidate) => candidate.id === familyId);
  const close = () => {
    navigate(routes.adminProductFamilies);
  };

  let body;
  if (!familyId) {
    body = <ProductFamilyForm onSaved={close} />;
  } else if (families.isSuccess && family) {
    body = <ProductFamilyForm key={family.version} family={family} onSaved={close} />;
  } else if (families.isError || (families.isSuccess && !family)) {
    body = <ErrorState error={families.error} onRetry={() => void families.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer
      open
      title={familyId ? t('admin:productFamilies.edit') : t('admin:productFamilies.new')}
      onClose={close}
    >
      {body}
    </ResponsiveFormContainer>
  );
}
