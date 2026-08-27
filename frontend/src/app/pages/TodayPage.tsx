import { useTranslation } from 'react-i18next';

import { PageHeader } from '@/components/shared/PageHeader';
import { useSessionStore } from '@/features/auth';

/** Placeholder until the activities change delivers "Mi día". */
export function TodayPage() {
  const { t } = useTranslation();
  const user = useSessionStore((state) => state.user);
  const withoutScope =
    user?.role === 'sales_rep' &&
    (user.territory_ids.length === 0 || user.division_ids.length === 0);
  return (
    <>
      <PageHeader title={t('today.title')} />
      {withoutScope ? (
        <p
          role="note"
          className="mt-3 rounded-md bg-accent px-3 py-2 text-sm text-accent-foreground"
        >
          {t('auth:scopeWarning')}
        </p>
      ) : null}
      <p className="py-6 text-muted-foreground">{t('today.placeholder')}</p>
    </>
  );
}
