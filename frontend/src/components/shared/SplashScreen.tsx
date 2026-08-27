import { useTranslation } from 'react-i18next';

import { Skeleton } from '@/components/ui/skeleton';

export function SplashScreen() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-dvh flex-col gap-4 p-4" role="status" aria-label={t('app.loading')}>
      <Skeleton className="h-10 w-1/2" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
