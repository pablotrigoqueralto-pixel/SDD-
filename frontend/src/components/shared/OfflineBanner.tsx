import { WifiOff } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useOnlineStatus } from '@/hooks/useOnlineStatus';

export function OfflineBanner() {
  const { t } = useTranslation();
  const online = useOnlineStatus();
  if (online) return null;
  return (
    <div
      role="status"
      className="flex items-center gap-2 bg-warning px-4 py-2 text-sm font-medium text-warning-foreground"
    >
      <WifiOff className="size-4 shrink-0" aria-hidden="true" />
      <span>{t('offline.banner')}</span>
    </div>
  );
}
