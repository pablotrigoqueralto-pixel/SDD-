import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

import { useTerritories } from '../../territories/queries';
import { ROLES, type Role, type UserRead } from '../../types';
import type { UserListFilters } from '../api';
import { useUsers } from '../queries';

export function UserListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const filters: UserListFilters = {
    q: params.get('q') ?? '',
    role: (params.get('role') ?? '') as Role | '',
    is_active: (params.get('is_active') ?? '') as UserListFilters['is_active'],
  };
  const users = useUsers(filters);
  const territories = useTerritories();
  const territoryName = (id: string) =>
    territories.data?.items.find((territory) => territory.id === id)?.name ?? '';

  const setFilter = (key: keyof UserListFilters, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const columns: DataListColumn<UserRead>[] = [
    { key: 'full_name', header: t('admin:users.form.fullName'), cell: (user) => user.full_name },
    { key: 'email', header: t('admin:users.form.email'), cell: (user) => user.email },
    { key: 'role', header: t('admin:users.form.role'), cell: (user) => t(`roles.${user.role}`) },
    {
      key: 'territories',
      header: t('admin:users.form.territories'),
      cell: (user) => user.territory_ids.map(territoryName).filter(Boolean).join(', '),
    },
    {
      key: 'status',
      header: t('admin:users.filterActive'),
      hideOnCard: true, // the card title already carries the badge
      cell: (user) =>
        user.is_active ? null : <Badge variant="secondary">{t('status.inactive')}</Badge>,
    },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.adminUserNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('admin:users.new')}
    </Button>
  );

  return (
    <>
      <PageHeader title={t('admin:users.title')} backTo={routes.admin} action={newButton} />
      <div className="flex flex-col gap-3 py-3 lg:flex-row">
        <Input
          type="search"
          aria-label={t('actions.search')}
          placeholder={t('admin:users.searchPlaceholder')}
          value={filters.q ?? ''}
          onChange={(event) => {
            setFilter('q', event.target.value);
          }}
          className="min-h-touch lg:max-w-xs"
        />
        <NativeSelect
          aria-label={t('admin:users.filterRole')}
          value={filters.role ?? ''}
          onChange={(event) => {
            setFilter('role', event.target.value);
          }}
          className="lg:w-56"
        >
          <option value="">{t('admin:users.allRoles')}</option>
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {t(`roles.${role}`)}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect
          aria-label={t('admin:users.filterActive')}
          value={filters.is_active ?? ''}
          onChange={(event) => {
            setFilter('is_active', event.target.value);
          }}
          className="lg:w-48"
        >
          <option value="">{t('admin:users.all')}</option>
          <option value="true">{t('admin:users.onlyActive')}</option>
          <option value="false">{t('admin:users.onlyInactive')}</option>
        </NativeSelect>
      </div>
      <DataList
        items={users.data?.items}
        columns={columns}
        getKey={(user) => user.id}
        renderTitle={(user) => (
          <span className="flex items-center gap-2">
            {user.full_name}
            {user.is_active ? null : <Badge variant="secondary">{t('status.inactive')}</Badge>}
          </span>
        )}
        onSelect={(user) => {
          navigate(routes.adminUser(user.id));
        }}
        isLoading={users.isPending}
        error={users.error}
        onRetry={() => void users.refetch()}
        emptyTitle={t('admin:users.empty')}
        emptyAction={newButton}
      />
      <Outlet />
    </>
  );
}
