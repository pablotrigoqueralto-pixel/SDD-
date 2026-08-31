import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/badge';
import { useSpecialties } from '@/features/reference';

import type { ContactRead } from '../api';

interface ContactSpecialtiesProps {
  contacts: ContactRead[] | undefined;
}

/**
 * The specialties a centre works in are derived from its contacts, never stored:
 * one badge per distinct specialty, nothing at all when no contact has one.
 */
export function ContactSpecialties({ contacts }: ContactSpecialtiesProps) {
  const { t } = useTranslation();
  const specialties = useSpecialties();
  const ids = [...new Set((contacts ?? []).map((c) => c.specialty_id).filter(Boolean))];
  const named = ids
    .map((id) => specialties.data?.find((specialty) => specialty.id === id))
    .filter((specialty) => specialty !== undefined);
  if (named.length === 0) return null;

  return (
    <ul className="mb-3 flex flex-wrap gap-1" aria-label={t('accounts:detail.specialties')}>
      {named.map((specialty) => (
        <li key={specialty.id}>
          <Badge variant="secondary">{specialty.name_es}</Badge>
        </li>
      ))}
    </ul>
  );
}
