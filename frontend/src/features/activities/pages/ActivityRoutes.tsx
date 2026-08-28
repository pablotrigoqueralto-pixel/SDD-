import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { ResponsiveFormContainer } from '@/components/shared/ResponsiveFormContainer';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useAccount,
  useAccounts,
  useIsManager,
  useIsStaff,
  type AccountRead,
} from '@/features/accounts';
import { useSessionStore } from '@/features/auth';

import { ActivityActions } from '../components/ActivityActions';
import { ActivityCard } from '../components/ActivityCard';
import { ActivityForm } from '../components/ActivityForm';
import { useActivity } from '../queries';
import { isWithinEditWindow } from '../schemas';

/** /centros/:id/actividades/nueva — the centre is known. */
export function ActivityNewRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { accountId } = useParams<{ accountId: string }>();
  const [searchParams] = useSearchParams();
  const opportunityId = searchParams.get('opportunity_id') ?? undefined;
  const account = useAccount(accountId);
  const close = () => {
    if (opportunityId) {
      navigate(routes.opportunity(opportunityId));
    } else {
      navigate(routes.account(accountId ?? ''));
    }
  };
  let body;
  if (account.isSuccess) {
    body = (
      <ActivityForm
        account={account.data}
        {...(opportunityId ? { opportunityId } : {})}
        onSaved={close}
      />
    );
  } else if (account.isError) {
    body = <ErrorState error={account.error} onRetry={() => void account.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }
  return (
    <ResponsiveFormContainer open title={t('activities:new')} onClose={close}>
      {body}
    </ResponsiveFormContainer>
  );
}

/** /hoy/nueva — pick the centre first (search), then the same form. */
export function TodayNewRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [picked, setPicked] = useState<AccountRead | null>(null);
  const results = useAccounts({ q: query, page_size: 10 });
  const close = () => {
    navigate(routes.today);
  };
  return (
    <ResponsiveFormContainer open title={t('activities:new')} onClose={close}>
      {picked ? (
        <ActivityForm account={picked} onSaved={close} />
      ) : (
        <div className="flex flex-col gap-3">
          <Input
            type="search"
            aria-label={t('activities:form.searchAccount')}
            placeholder={t('activities:form.searchAccount')}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            className="min-h-touch"
          />
          <p className="text-sm text-muted-foreground">{t('activities:form.selectAccount')}</p>
          <ul className="flex flex-col gap-1">
            {results.data?.items.map((summary) => (
              <li key={summary.id}>
                <AccountPickButton accountId={summary.id} name={summary.name} onPick={setPicked} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </ResponsiveFormContainer>
  );
}

function AccountPickButton({
  accountId,
  name,
  onPick,
}: {
  accountId: string;
  name: string;
  onPick: (account: AccountRead) => void;
}) {
  const account = useAccount(accountId);
  return (
    <button
      type="button"
      className="min-h-touch w-full rounded-md border px-3 text-left text-sm hover:bg-muted disabled:opacity-60"
      disabled={!account.data}
      onClick={() => {
        if (account.data) onPick(account.data);
      }}
    >
      {name}
    </button>
  );
}

/** /centros/:id/actividades/:activityId — edit, or read-only when locked, plus actions. */
export function ActivityDetailRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { accountId, activityId } = useParams<{ accountId: string; activityId: string }>();
  const user = useSessionStore((state) => state.user);
  const isManager = useIsManager();
  const isStaff = useIsStaff();
  const account = useAccount(accountId);
  const activity = useActivity(activityId);
  const close = () => {
    navigate(routes.account(accountId ?? ''));
  };

  let body;
  if (account.isSuccess && activity.isSuccess) {
    const data = activity.data;
    const owns = data.owner_id === user?.id;
    const editable =
      isManager ||
      (!isStaff &&
        owns &&
        data.status !== 'cancelled' &&
        (data.status !== 'done' || isWithinEditWindow(data.done_at)));
    body = editable ? (
      <div className="flex flex-col gap-4">
        <ActivityActions activity={data} withCancel />
        <ActivityForm key={data.version} account={account.data} activity={data} onSaved={close} />
      </div>
    ) : (
      <div className="flex flex-col gap-3">
        <ActivityCard activity={data} linkToDetail={false} />
        <p role="note" className="text-sm text-muted-foreground">
          {t('activities:locked')}
        </p>
      </div>
    );
  } else if (account.isError || activity.isError) {
    const failed = account.isError ? account : activity;
    body = <ErrorState error={failed.error} onRetry={() => void failed.refetch()} />;
  } else {
    body = <Skeleton className="h-40 w-full" />;
  }

  return (
    <ResponsiveFormContainer open title={t('activities:edit')} onClose={close}>
      {body}
    </ResponsiveFormContainer>
  );
}
