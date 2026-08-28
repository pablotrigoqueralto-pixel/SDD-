import { Mail, Pencil, Phone, ShieldOff } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useIsManager, useIsStaff } from '@/features/accounts';
import { labelOf, useDivisions, useJobTitles } from '@/features/reference';
import { toast } from '@/hooks/use-toast';

import type { ContactRead } from '../api';
import { useAnonymiseContact } from '../queries';
import { ConsentBadge } from './ConsentBadge';

interface ContactCardProps {
  contact: ContactRead;
}

/** One tap to call or write; edit and (managers) anonymise. */
export function ContactCard({ contact }: ContactCardProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const jobTitles = useJobTitles();
  const divisions = useDivisions();
  const isManager = useIsManager();
  const isStaff = useIsStaff();
  const anonymise = useAnonymiseContact();
  const fullName = `${contact.first_name} ${contact.last_name}`;
  const phone = contact.mobile ?? contact.landline;
  const subtitle = [
    labelOf(jobTitles.data, contact.job_title_id, (title) => title.name_es),
    labelOf(divisions.data, contact.division_id, (division) => division.name_es),
  ]
    .filter(Boolean)
    .join(' · ');
  const canEdit = !contact.anonymised_at && (isManager || !isStaff);

  const handleAnonymise = async () => {
    if (!window.confirm(t('contacts:anonymiseConfirm'))) return;
    await anonymise.mutateAsync({
      id: contact.id,
      accountId: contact.account_id,
      version: contact.version,
    });
    toast({ description: t('contacts:anonymised') });
  };

  return (
    <article className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{fullName}</span>
        {contact.is_primary ? <Badge>{t('contacts:primary')}</Badge> : null}
        {contact.anonymised_at ? (
          <Badge variant="outline">{t('contacts:anonymisedBadge')}</Badge>
        ) : contact.is_active ? null : (
          <Badge variant="outline">{t('contacts:inactive')}</Badge>
        )}
        <ConsentBadge consent={contact.consent} />
      </div>
      {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      <div className="flex flex-wrap gap-2">
        {phone ? (
          <Button asChild variant="outline" size="sm" className="min-h-touch">
            <a href={`tel:${phone}`} aria-label={t('contacts:call', { name: fullName })}>
              <Phone className="size-4" aria-hidden="true" />
              {phone}
            </a>
          </Button>
        ) : null}
        {contact.email ? (
          <Button asChild variant="outline" size="sm" className="min-h-touch">
            <a
              href={`mailto:${contact.email}`}
              aria-label={t('contacts:email', { name: fullName })}
            >
              <Mail className="size-4" aria-hidden="true" />
              {contact.email}
            </a>
          </Button>
        ) : null}
        {canEdit ? (
          <Button
            variant="ghost"
            size="sm"
            className="min-h-touch"
            onClick={() => {
              navigate(routes.contactEdit(contact.account_id, contact.id));
            }}
          >
            <Pencil className="size-4" aria-hidden="true" />
            {t('actions.edit')}
          </Button>
        ) : null}
        {isManager && !contact.anonymised_at ? (
          <Button
            variant="ghost"
            size="sm"
            className="min-h-touch text-destructive"
            disabled={anonymise.isPending}
            onClick={() => void handleAnonymise()}
          >
            <ShieldOff className="size-4" aria-hidden="true" />
            {t('contacts:anonymise')}
          </Button>
        ) : null}
      </div>
    </article>
  );
}
