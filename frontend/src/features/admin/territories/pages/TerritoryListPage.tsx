import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { provinceName } from '@/lib/provinces';

import type { TerritoryRead } from '../../types';
import { useTerritories } from '../queries';

export function TerritoryListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const territories = useTerritories();

  const columns: DataListColumn<TerritoryRead>[] = [
    { key: 'name', header: t('admin:territories.form.name'), cell: (territory) => territory.name },
    {
      key: 'provinces',
      header: t('admin:territories.form.provinces'),
      cell: (territory) => territory.provinces.map(provinceName).join(', '),
    },
    {
      key: 'users',
      header: t('admin:hub.users'),
      cell: (territory) => t('count.users', { count: territory.user_count }),
    },
    {
      key: 'status',
      header: t('admin:users.filterActive'),
      cell: (territory) =>
        territory.is_active ? null : <Badge variant="secondary">{t('status.inactive')}</Badge>,
    },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.adminTerritoryNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('admin:territories.new')}
    </Button>
  );

  return (
    <>
      <PageHeader title={t('admin:territories.title')} backTo={routes.admin} action={newButton} />
      <div className="py-3">
        <DataList
          items={territories.data?.items}
          columns={columns}
          getKey={(territory) => territory.id}
          onSelect={(territory) => {
            navigate(routes.adminTerritory(territory.id));
          }}
          isLoading={territories.isPending}
          error={territories.error}
          onRetry={() => void territories.refetch()}
          emptyTitle={t('admin:territories.empty')}
          emptyAction={newButton}
        />
      </div>
      <Outlet />
    </>
  );
}
