import { MapPin } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet, useNavigate, useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { ErrorState } from '@/components/shared/ErrorState';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { TimelineSection } from '@/features/activities';
import { ContactCard, useAccountContacts } from '@/features/contacts';
import { labelOf, useBrands, useDivisions } from '@/features/reference';
import { toProblem } from '@/lib/problem';
import { PROVINCES } from '@/lib/provinces';

import type { AccountRead } from '../api';
import { AccountHeader } from '../components/AccountHeader';
import { AccountSection } from '../components/AccountSection';
import { OpportunitiesSection } from '../components/OpportunitiesSection';
import { PlaceholderSection } from '../components/PlaceholderSection';
import { useIsManager, useIsStaff } from '../hooks';
import { useAccount } from '../queries';

function provinceName(code: string): string {
  return PROVINCES.find((province) => province.code === code)?.name ?? code;
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex flex-col">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function AccountData({ account }: { account: AccountRead }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const divisions = useDivisions();
  const brands = useBrands();
  const isStaff = useIsStaff();
  const isManager = useIsManager();
  const primaryAddress = [account.street, account.postal_code, account.city]
    .filter(Boolean)
    .join(', ');
  return (
    <div className="flex flex-col gap-3 text-sm">
      <dl className="grid gap-3 sm:grid-cols-2">
        <Field
          label={t('accounts:detail.primaryAddress')}
          value={`${primaryAddress ? `${primaryAddress} · ` : ''}${provinceName(account.province_code)}`}
        />
        <Field label={t('accounts:form.taxId')} value={account.tax_id} />
        <Field label={t('accounts:form.customerCode')} value={account.customer_code} />
        <Field label={t('accounts:form.phone')} value={account.phone} />
        <Field label={t('accounts:form.email')} value={account.email} />
        <Field label={t('accounts:form.website')} value={account.website} />
        <Field
          label={t('accounts:form.divisions')}
          value={account.division_ids
            .map((id) => labelOf(divisions.data, id, (division) => division.name_es))
            .join(', ')}
        />
        <Field
          label={t('accounts:form.brands')}
          value={account.brand_ids
            .map((id) => labelOf(brands.data, id, (brand) => brand.name))
            .join(', ')}
        />
      </dl>
      <div>
        <div className="flex items-center justify-between">
          <h3 className="text-xs text-muted-foreground">
            {t('accounts:detail.additionalAddresses')}
          </h3>
          {isStaff && !isManager ? null : (
            <Button
              variant="ghost"
              size="sm"
              className="min-h-touch"
              onClick={() => {
                navigate(routes.accountAddresses(account.id));
              }}
            >
              <MapPin className="size-4" aria-hidden="true" />
              {t('accounts:detail.editAddresses')}
            </Button>
          )}
        </div>
        {account.addresses.length === 0 ? (
          <p className="text-muted-foreground">{t('accounts:detail.noAddresses')}</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {account.addresses.map((address) => {
              const line = `${address.street}, ${address.postal_code} ${address.city} · ${provinceName(address.province_code)}`;
              return (
                <li key={address.label}>
                  <span className="font-medium">{address.label}</span>
                  {': '}
                  {line}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

/** 360º page: header with actions, then collapsible sections in a fixed order. */
export function AccountPage() {
  const { t } = useTranslation();
  const { accountId } = useParams<{ accountId: string }>();
  const account = useAccount(accountId);
  const contacts = useAccountContacts(accountId);
  const isStaff = useIsStaff();
  const isManager = useIsManager();

  if (account.isPending) {
    return (
      <div role="status" aria-busy="true" aria-label={t('app.loading')} className="py-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="mt-3 h-24 w-full" />
      </div>
    );
  }
  if (account.isError) {
    const problem = toProblem(account.error);
    if (problem.code === 'not_found') {
      return (
        <section className="py-10 text-center" role="alert">
          <h1 className="text-xl font-semibold">{t('accounts:notFoundTitle')}</h1>
          <p className="mt-2 text-muted-foreground">{t('accounts:notFoundDetail')}</p>
          <Link to={routes.accounts} className="mt-4 inline-block underline">
            {t('accounts:backToList')}
          </Link>
        </section>
      );
    }
    return <ErrorState error={account.error} onRetry={() => void account.refetch()} />;
  }

  const data = account.data;
  const sections = t('accounts:detail.sections', { returnObjects: true }) as Record<string, string>;
  const contactsSection = (
    <AccountSection
      sectionKey="contacts"
      title={sections.contacts ?? ''}
      count={contacts.data?.length}
    >
      {contacts.isPending ? (
        <Skeleton className="h-16 w-full" />
      ) : contacts.isError ? (
        <ErrorState error={contacts.error} onRetry={() => void contacts.refetch()} />
      ) : contacts.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('accounts:detail.noContacts')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {contacts.data.map((contact) => (
            <li key={contact.id}>
              <ContactCard contact={contact} />
            </li>
          ))}
        </ul>
      )}
    </AccountSection>
  );
  const activitiesSection = (
    <AccountSection sectionKey="activities" title={sections.activities ?? ''}>
      <TimelineSection accountId={data.id} canWrite={!isStaff || isManager} />
    </AccountSection>
  );
  const dataSection = (
    <AccountSection sectionKey="data" title={sections.data ?? ''}>
      <AccountData account={data} />
    </AccountSection>
  );
  const notesSection = (
    <AccountSection sectionKey="notes" title={sections.notes ?? ''}>
      <p className="whitespace-pre-line text-sm">
        {data.notes ?? (
          <span className="text-muted-foreground">{t('accounts:detail.noNotes')}</span>
        )}
      </p>
    </AccountSection>
  );
  const opportunitiesSection = (
    <AccountSection sectionKey="opportunities" title={sections.opportunities ?? ''}>
      <OpportunitiesSection accountId={data.id} />
    </AccountSection>
  );
  const placeholders = (
    <>
      <PlaceholderSection sectionKey="quotes" title={sections.quotes ?? ''} />
      <PlaceholderSection sectionKey="equipment" title={sections.equipment ?? ''} />
    </>
  );

  return (
    <>
      <AccountHeader account={data} />
      <div className="flex flex-col gap-3 pb-4 lg:hidden">
        {activitiesSection}
        {opportunitiesSection}
        {contactsSection}
        {dataSection}
        {placeholders}
        {notesSection}
      </div>
      <div className="hidden gap-3 pb-4 lg:grid lg:grid-cols-3">
        <div className="flex flex-col gap-3">
          {dataSection}
          {notesSection}
        </div>
        <div className="flex flex-col gap-3 lg:col-span-2">
          {activitiesSection}
          {opportunitiesSection}
          {contactsSection}
          {placeholders}
        </div>
      </div>
      <Outlet />
    </>
  );
}
