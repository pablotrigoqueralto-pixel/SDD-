import { CalendarPlus, Pencil, UserPlus, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatWhen } from '@/features/activities';
import { labelOf, useAccountTypes } from '@/features/reference';
import { PROVINCES } from '@/lib/provinces';

import type { AccountRead } from '../api';
import { useIsManager, useIsStaff } from '../hooks';

interface AccountHeaderProps {
  account: AccountRead;
}

type Badgeable = Pick<AccountRead, 'is_active' | 'owner_id' | 'territory_mismatch'>;

export function AccountBadges({ account }: { account: Badgeable }) {
  const { t } = useTranslation();
  return (
    <>
      {account.is_active ? null : <Badge variant="outline">{t('accounts:badges.inactive')}</Badge>}
      {account.owner_id ? null : (
        <Badge variant="secondary">{t('accounts:badges.unassigned')}</Badge>
      )}
      {account.territory_mismatch ? (
        <Badge variant="destructive" title={t('accounts:badges.territoryMismatchHint')}>
          {t('accounts:badges.territoryMismatch')}
        </Badge>
      ) : null}
    </>
  );
}

/** Name, type, place, territory and owner plus the two actions that are always reachable. */
export function AccountHeader({ account }: AccountHeaderProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const accountTypes = useAccountTypes();
  const isStaff = useIsStaff();
  const isManager = useIsManager();
  const province = PROVINCES.find((item) => item.code === account.province_code)?.name ?? '';
  const place = [account.city, province].filter(Boolean).join(', ');

  const actions = (
    <div className="flex shrink-0 gap-1 sm:gap-2">
      {isManager ? (
        <Button
          variant="outline"
          size="sm"
          className="min-h-touch"
          aria-label={t('accounts:detail.reassign')}
          onClick={() => {
            navigate(routes.accountAssign(account.id));
          }}
        >
          <Users className="size-4" aria-hidden="true" />
          <span className="hidden sm:inline">{t('accounts:detail.reassign')}</span>
        </Button>
      ) : null}
      <Button
        variant="outline"
        size="sm"
        className="min-h-touch"
        aria-label={t('actions.edit')}
        onClick={() => {
          navigate(routes.accountEdit(account.id));
        }}
      >
        <Pencil className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">{t('actions.edit')}</span>
      </Button>
      {isStaff && !isManager ? null : (
        <>
          <Button
            variant="outline"
            size="sm"
            className="min-h-touch"
            aria-label={t('contacts:new')}
            onClick={() => {
              navigate(routes.contactNew(account.id));
            }}
          >
            <UserPlus className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">{t('contacts:new')}</span>
          </Button>
          <Button
            size="sm"
            className="min-h-touch"
            aria-label={t('activities:new')}
            onClick={() => {
              navigate(routes.activityNew(account.id));
            }}
          >
            <CalendarPlus className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">{t('activities:new')}</span>
          </Button>
        </>
      )}
    </div>
  );

  return (
    <>
      <PageHeader title={account.name} backTo={routes.accounts} action={actions} />
      <div className="flex flex-col gap-1 py-3 text-sm text-muted-foreground">
        <p>
          {labelOf(accountTypes.data, account.account_type_id, (type) => type.name_es)}
          {place ? ` · ${place}` : ''}
        </p>
        <p>
          {t('accounts:detail.territory')}
          {': '}
          {account.territory_name ?? t('accounts:detail.unassignedTerritory')}
          {' · '}
          {t('accounts:detail.owner')}
          {': '}
          {account.owner_name ?? t('accounts:detail.unassignedOwner')}
        </p>
        <p>
          {t('activities:recency.lastContact')}
          {': '}
          {account.last_contact_at
            ? formatWhen(account.last_contact_at, 'date')
            : t('activities:recency.never')}
          {account.next_activity_at
            ? ` · ${t('activities:recency.nextActivity')}: ${formatWhen(account.next_activity_at)}`
            : ''}
        </p>
        <div className="flex flex-wrap gap-1">
          <AccountBadges account={account} />
        </div>
      </div>
    </>
  );
}
