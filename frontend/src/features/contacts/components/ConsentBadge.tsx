import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/badge';

import type { ContactRead } from '../api';

const VARIANTS = { granted: 'default', denied: 'destructive', unknown: 'outline' } as const;

export function ConsentBadge({ consent }: { consent: ContactRead['consent'] }) {
  const { t } = useTranslation();
  const date = consent.at ? new Date(consent.at).toLocaleDateString('es-ES') : null;
  return (
    <Badge
      variant={VARIANTS[consent.status]}
      title={date ? t('contacts:consent.recordedBy', { date }) : undefined}
    >
      {t(`contacts:consent.statuses.${consent.status}`)}
    </Badge>
  );
}
