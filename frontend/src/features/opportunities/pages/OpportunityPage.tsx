import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet, useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { NativeSelect } from '@/components/shared/NativeSelect';
import { PageHeader } from '@/components/shared/PageHeader';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useIsManager } from '@/features/accounts';
import { ActivityCard, formatWhen, useActivities } from '@/features/activities';
import { useUsers } from '@/features/admin';
import { labelOf, useBrands, useLossReasons, usePipelines } from '@/features/reference';
import { toast } from '@/hooks/use-toast';

import { AmountText } from '../components/AmountText';
import { LinesEditor } from '../components/LinesEditor';
import { StageBadge } from '../components/StageBadge';
import { StageHistory } from '../components/StageHistory';
import { StagePicker } from '../components/StagePicker';
import { useCanWriteOpportunity } from '../hooks';
import { useAssignOpportunity, useOpportunity, useReopenOpportunity, useSetAtRisk } from '../queries';

export function OpportunityPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { opportunityId } = useParams<{ opportunityId: string }>();
  const query = useOpportunity(opportunityId);
  const canWrite = useCanWriteOpportunity(query.data);
  const isManager = useIsManager();
  const lossReasons = useLossReasons();
  const brands = useBrands();
  const setAtRisk = useSetAtRisk();
  const [reassignOpen, setReassignOpen] = useState(false);
  const [reopenOpen, setReopenOpen] = useState(false);

  if (query.isError) {
    return (
      <>
        <PageHeader title={t('opportunities:opportunity')} backTo={routes.opportunities} />
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      </>
    );
  }
  if (!query.data) {
    return (
      <>
        <PageHeader title={t('opportunities:opportunity')} backTo={routes.opportunities} />
        <Skeleton className="h-40 w-full" />
      </>
    );
  }
  const opportunity = query.data;
  const closed = opportunity.status !== 'open';
  const canToggleAtRisk =
    canWrite && opportunity.status === 'won' && opportunity.pipeline_name === 'Consumibles';

  const toggleAtRisk = async () => {
    await setAtRisk.mutateAsync({
      id: opportunity.id,
      accountId: opportunity.account_id,
      version: opportunity.version,
      flag: !opportunity.is_at_risk,
    });
    toast({
      description: opportunity.is_at_risk
        ? t('opportunities:atRiskCleared')
        : t('opportunities:atRiskSet'),
    });
  };

  return (
    <>
      <PageHeader
        title={opportunity.name}
        backTo={routes.opportunities}
        action={
          canWrite && !closed ? (
            <span className="flex gap-2">
              <Button
                size="sm"
                className="min-h-touch"
                onClick={() => {
                  navigate('ganar');
                }}
              >
                {t('opportunities:actions.win')}
              </Button>
              <Button
                size="sm"
                variant="destructive"
                className="min-h-touch"
                onClick={() => {
                  navigate('perder');
                }}
              >
                {t('opportunities:actions.lose')}
              </Button>
            </span>
          ) : undefined
        }
      />
      <div className="flex flex-col gap-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <AmountText amount={opportunity.amount} className="text-2xl font-bold tabular-nums" />
          <StageBadge opportunity={opportunity} />
          <span className="text-sm text-muted-foreground">
            {t('opportunities:list.daysInStage', { count: opportunity.days_in_stage })}
          </span>
          <Link to={routes.account(opportunity.account_id)} className="text-sm underline">
            {opportunity.account_name}
          </Link>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StagePicker opportunity={opportunity} disabled={!canWrite} />
          {canWrite && !closed ? (
            <Button
              variant="outline"
              size="sm"
              className="min-h-touch"
              onClick={() => {
                navigate('editar');
              }}
            >
              {t('actions.edit')}
            </Button>
          ) : null}
          {canToggleAtRisk ? (
            <Button
              variant="outline"
              size="sm"
              className="min-h-touch"
              disabled={setAtRisk.isPending}
              onClick={() => void toggleAtRisk()}
            >
              {opportunity.is_at_risk
                ? t('opportunities:actions.clearAtRisk')
                : t('opportunities:actions.atRisk')}
            </Button>
          ) : null}
          {isManager ? (
            <>
              <Button
                variant="outline"
                size="sm"
                className="min-h-touch"
                onClick={() => {
                  setReassignOpen(true);
                }}
              >
                {t('opportunities:actions.reassign')}
              </Button>
              {closed ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="min-h-touch"
                  onClick={() => {
                    setReopenOpen(true);
                  }}
                >
                  {t('opportunities:actions.reopen')}
                </Button>
              ) : null}
            </>
          ) : null}
        </div>
        {opportunity.status === 'won' && opportunity.won_at ? (
          <p className="rounded-lg border bg-muted/40 p-3 text-sm">
            {t('opportunities:sheet.closedWon', {
              date: formatWhen(opportunity.won_at, 'date'),
              amount: opportunity.won_amount ?? opportunity.amount,
            })}
          </p>
        ) : null}
        {opportunity.status === 'lost' && opportunity.lost_at ? (
          <div className="rounded-lg border bg-muted/40 p-3 text-sm">
            <p>{t('opportunities:sheet.closedLost', { date: formatWhen(opportunity.lost_at, 'date') })}</p>
            <p>
              {t('opportunities:sheet.lossReason')}
              {': '}
              {labelOf(lossReasons.data, opportunity.loss_reason_id, (reason) => reason.name_es)}
            </p>
            {opportunity.competitor_brand_id ? (
              <p>
                {t('opportunities:sheet.competitorBrand')}
                {': '}
                {labelOf(brands.data, opportunity.competitor_brand_id, (brand) => brand.name)}
              </p>
            ) : null}
            {opportunity.loss_note ? (
              <p>
                {t('opportunities:sheet.lossNote')}
                {': '}
                {opportunity.loss_note}
              </p>
            ) : null}
          </div>
        ) : null}

        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">{t('opportunities:sheet.data')}</h2>
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            <div className="flex gap-2">
              <dt className="text-muted-foreground">{t('opportunities:list.closeDate')}</dt>
              <dd>{formatWhen(opportunity.expected_close_date, 'date')}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">{t('opportunities:list.owner')}</dt>
              <dd>{opportunity.owner_name}</dd>
            </div>
            {opportunity.lines.length === 0 ? (
              <div className="flex gap-2">
                <dt className="text-muted-foreground">
                  {t('opportunities:form.estimatedAmount')}
                </dt>
                <dd>
                  <AmountText amount={opportunity.estimated_amount} />
                </dd>
              </div>
            ) : null}
            {opportunity.is_tender ? (
              <>
                {opportunity.tender_reference ? (
                  <div className="flex gap-2">
                    <dt className="text-muted-foreground">
                      {t('opportunities:form.tenderReference')}
                    </dt>
                    <dd>{opportunity.tender_reference}</dd>
                  </div>
                ) : null}
                {opportunity.tender_deadline ? (
                  <div className="flex gap-2">
                    <dt className="text-muted-foreground">
                      {t('opportunities:form.tenderDeadline')}
                    </dt>
                    <dd>{formatWhen(opportunity.tender_deadline, 'date')}</dd>
                  </div>
                ) : null}
                {opportunity.estimated_award_date ? (
                  <div className="flex gap-2">
                    <dt className="text-muted-foreground">{t('opportunities:form.awardDate')}</dt>
                    <dd>{formatWhen(opportunity.estimated_award_date, 'date')}</dd>
                  </div>
                ) : null}
              </>
            ) : null}
            {opportunity.description ? (
              <div className="flex gap-2 sm:col-span-2">
                <dt className="text-muted-foreground">{t('opportunities:form.description')}</dt>
                <dd>{opportunity.description}</dd>
              </div>
            ) : null}
          </dl>
        </section>

        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">{t('opportunities:sheet.products')}</h2>
          <LinesEditor opportunity={opportunity} canWrite={canWrite && !closed} />
        </section>

        <OpportunityActivities opportunityId={opportunity.id} accountId={opportunity.account_id} />

        <section className="flex flex-col gap-2">
          <h2 className="text-base font-semibold">{t('opportunities:sheet.history')}</h2>
          <StageHistory opportunity={opportunity} />
        </section>
      </div>
      {reassignOpen ? (
        <ReassignDialog
          opportunityId={opportunity.id}
          accountId={opportunity.account_id}
          version={opportunity.version}
          onClose={() => {
            setReassignOpen(false);
          }}
        />
      ) : null}
      {reopenOpen ? (
        <ReopenDialog
          opportunityId={opportunity.id}
          accountId={opportunity.account_id}
          pipelineId={opportunity.pipeline_id}
          version={opportunity.version}
          onClose={() => {
            setReopenOpen(false);
          }}
        />
      ) : null}
      <Outlet />
    </>
  );
}

function OpportunityActivities({
  opportunityId,
  accountId,
}: {
  opportunityId: string;
  accountId: string;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const activities = useActivities({ opportunity_id: opportunityId });
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">{t('opportunities:sheet.activities')}</h2>
        <Button
          variant="outline"
          size="sm"
          className="min-h-touch"
          onClick={() => {
            navigate(
              `${routes.activityNew(accountId)}?opportunity_id=${encodeURIComponent(opportunityId)}`,
            );
          }}
        >
          {t('opportunities:sheet.newActivity')}
        </Button>
      </div>
      {activities.data && activities.data.items.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {activities.data.items.map((activity) => (
            <li key={activity.id}>
              <ActivityCard activity={activity} showAccount={false} whenVariant="both" />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{t('opportunities:sheet.noActivities')}</p>
      )}
    </section>
  );
}

function ReassignDialog({
  opportunityId,
  accountId,
  version,
  onClose,
}: {
  opportunityId: string;
  accountId: string;
  version: number;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const assign = useAssignOpportunity();
  const reps = useUsers({ role: 'sales_rep', is_active: 'true', page_size: 200 });
  const [ownerId, setOwnerId] = useState('');
  return (
    <ResponsiveFormContainer open title={t('opportunities:assign.title')} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <NativeSelect
          aria-label={t('opportunities:assign.owner')}
          value={ownerId}
          onChange={(event) => {
            setOwnerId(event.target.value);
          }}
        >
          <option value="">{t('opportunities:assign.owner')}</option>
          {reps.data?.items.map((rep) => (
            <option key={rep.id} value={rep.id}>
              {rep.full_name}
            </option>
          ))}
        </NativeSelect>
        <Button
          className="min-h-touch"
          disabled={!ownerId || assign.isPending}
          onClick={() =>
            void assign
              .mutateAsync({ id: opportunityId, accountId, version, ownerId })
              .then(() => {
                toast({ description: t('opportunities:reassigned') });
                onClose();
              })
          }
        >
          {t('actions.save')}
        </Button>
      </div>
    </ResponsiveFormContainer>
  );
}

function ReopenDialog({
  opportunityId,
  accountId,
  pipelineId,
  version,
  onClose,
}: {
  opportunityId: string;
  accountId: string;
  pipelineId: string;
  version: number;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const reopen = useReopenOpportunity();
  const pipelines = usePipelines();
  const [stageId, setStageId] = useState('');
  const openStages = (
    pipelines.data?.find((pipeline) => pipeline.id === pipelineId)?.stages ?? []
  ).filter((stage) => !stage.is_won && !stage.is_lost && !stage.is_at_risk && stage.is_active);
  return (
    <ResponsiveFormContainer open title={t('opportunities:reopen.title')} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <NativeSelect
          aria-label={t('opportunities:reopen.stage')}
          value={stageId}
          onChange={(event) => {
            setStageId(event.target.value);
          }}
        >
          <option value="">{t('opportunities:reopen.stage')}</option>
          {openStages.map((stage) => (
            <option key={stage.id} value={stage.id}>
              {stage.name_es}
            </option>
          ))}
        </NativeSelect>
        <Button
          className="min-h-touch"
          disabled={!stageId || reopen.isPending}
          onClick={() =>
            void reopen
              .mutateAsync({ id: opportunityId, accountId, version, stageId })
              .then(() => {
                toast({ description: t('opportunities:reopened') });
                onClose();
              })
          }
        >
          {t('actions.save')}
        </Button>
      </div>
    </ResponsiveFormContainer>
  );
}
