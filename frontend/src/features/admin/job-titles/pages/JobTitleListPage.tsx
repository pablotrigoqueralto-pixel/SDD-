import { Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Outlet, useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { DataList, type DataListColumn } from '@/components/shared/DataList';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

import type { JobTitleRead } from '../api';
import { JobTitleForm } from '../components/JobTitleForm';
import { useJobTitleList } from '../queries';

export function JobTitleListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const titles = useJobTitleList();

  const columns: DataListColumn<JobTitleRead>[] = [
    { key: 'name', header: t('admin:jobTitles.form.name'), cell: (title) => title.name_es },
    {
      key: 'status',
      header: t('admin:users.filterActive'),
      cell: (title) =>
        title.is_active ? null : <Badge variant="outline">{t('status.inactive')}</Badge>,
    },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.adminJobTitleNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('admin:jobTitles.new')}
    </Button>
  );

  return (
    <>
      <PageHeader title={t('admin:jobTitles.title')} backTo={routes.admin} action={newButton} />
      <div className="py-3">
        <DataList
          items={titles.data}
          columns={columns}
          getKey={(title) => title.id}
          onSelect={(title) => {
            navigate(routes.adminJobTitle(title.id));
          }}
          isLoading={titles.isPending}
          error={titles.error}
          onRetry={() => void titles.refetch()}
          emptyTitle={t('admin:jobTitles.empty')}
          emptyAction={newButton}
        />
      </div>
      <Outlet />
    </>
  );
}

/** /admin/cargos/nuevo and /admin/cargos/:id rendered over the list. */
export function JobTitleFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { jobTitleId } = useParams<{ jobTitleId: string }>();
  const titles = useJobTitleList();
  const title = titles.data?.find((candidate) => candidate.id === jobTitleId);
  const close = () => {
    navigate(routes.adminJobTitles);
  };

  let body;
  if (!jobTitleId) {
    body = <JobTitleForm onSaved={close} />;
  } else if (titles.isSuccess && title) {
    body = <JobTitleForm key={title.version} jobTitle={title} onSaved={close} />;
  } else if (titles.isError || (titles.isSuccess && !title)) {
    body = <ErrorState error={titles.error} onRetry={() => void titles.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer
      open
      title={jobTitleId ? t('admin:jobTitles.edit') : t('admin:jobTitles.new')}
      onClose={close}
    >
      {body}
    </ResponsiveFormContainer>
  );
}
