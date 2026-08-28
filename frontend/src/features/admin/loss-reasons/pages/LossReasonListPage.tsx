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

import type { LossReasonRead } from '../api';
import { LossReasonForm } from '../components/LossReasonForm';
import { useLossReasonList } from '../queries';

export function LossReasonListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const reasons = useLossReasonList();

  const badges = (reason: LossReasonRead) => (
    <span className="flex flex-wrap gap-1">
      {reason.requires_brand ? (
        <Badge variant="secondary">{t('admin:lossReasons.requiresBrand')}</Badge>
      ) : null}
      {reason.requires_note ? (
        <Badge variant="secondary">{t('admin:lossReasons.requiresNote')}</Badge>
      ) : null}
      {reason.is_active ? null : <Badge variant="outline">{t('status.inactive')}</Badge>}
    </span>
  );

  const columns: DataListColumn<LossReasonRead>[] = [
    { key: 'name', header: t('admin:lossReasons.form.name'), cell: (reason) => reason.name_es },
    { key: 'flags', header: t('admin:users.filterActive'), cell: badges },
  ];

  const newButton = (
    <Button
      size="sm"
      className="min-h-touch"
      onClick={() => {
        navigate(routes.adminLossReasonNew);
      }}
    >
      <Plus className="size-4" aria-hidden="true" />
      {t('admin:lossReasons.new')}
    </Button>
  );

  return (
    <>
      <PageHeader title={t('admin:lossReasons.title')} backTo={routes.admin} action={newButton} />
      <div className="py-3">
        <DataList
          items={reasons.data}
          columns={columns}
          getKey={(reason) => reason.id}
          onSelect={(reason) => {
            navigate(routes.adminLossReason(reason.id));
          }}
          isLoading={reasons.isPending}
          error={reasons.error}
          onRetry={() => void reasons.refetch()}
          emptyTitle={t('admin:lossReasons.empty')}
          emptyAction={newButton}
        />
      </div>
      <Outlet />
    </>
  );
}

/** /admin/motivos-perdida/nuevo and /admin/motivos-perdida/:id rendered over the list. */
export function LossReasonFormRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { reasonId } = useParams<{ reasonId: string }>();
  const reasons = useLossReasonList();
  const reason = reasons.data?.find((candidate) => candidate.id === reasonId);
  const close = () => {
    navigate(routes.adminLossReasons);
  };

  let body;
  if (!reasonId) {
    body = <LossReasonForm onSaved={close} />;
  } else if (reasons.isSuccess && reason) {
    body = <LossReasonForm key={reason.version} reason={reason} onSaved={close} />;
  } else if (reasons.isError || (reasons.isSuccess && !reason)) {
    body = <ErrorState error={reasons.error} onRetry={() => void reasons.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer
      open
      title={reasonId ? t('admin:lossReasons.edit') : t('admin:lossReasons.new')}
      onClose={close}
    >
      {body}
    </ResponsiveFormContainer>
  );
}
