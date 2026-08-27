import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import { isKnownErrorCode } from '@/lib/error-codes';
import { toProblem } from '@/lib/problem';

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const { t } = useTranslation();
  const problem = toProblem(error);
  const detail =
    isKnownErrorCode(problem.code) || problem.code === 'network_error'
      ? t(`errors:${problem.code}`)
      : t('states.errorDetail');
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-lg border px-6 py-10 text-center"
    >
      <p className="font-medium">{t('states.errorTitle')}</p>
      <p className="text-sm text-muted-foreground">{detail}</p>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry} className="min-h-touch">
          {t('actions.retry')}
        </Button>
      ) : null}
    </div>
  );
}
