import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { useSessionStore } from '@/store/session.store';

import { LoginForm } from '../components/LoginForm';

function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : routes.today;
}

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const status = useSessionStore((state) => state.status);
  const next = safeNext(params.get('next'));

  if (status === 'authenticated') {
    return <Navigate to={next} replace />;
  }

  return (
    <main className="flex min-h-dvh flex-col justify-center px-4 py-8">
      <div className="mx-auto w-full max-w-sm">
        <h1 className="mb-6 text-2xl font-semibold">{t('auth:login.title')}</h1>
        <LoginForm
          onSuccess={() => {
            navigate(next, { replace: true });
          }}
        />
      </div>
    </main>
  );
}
