import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { SplashScreen } from '@/components/shared/SplashScreen';
import { useSessionStore, type SessionUser } from '@/features/auth';

import { loginWithNext } from './routes';

/** Redirects anonymous users to /login and preserves the intended URL. */
export function AuthGuard() {
  const status = useSessionStore((state) => state.status);
  const location = useLocation();
  if (status === 'unknown') return <SplashScreen />;
  if (status === 'anonymous') {
    return <Navigate to={loginWithNext(location.pathname + location.search)} replace />;
  }
  return <Outlet />;
}

interface RoleGateProps {
  roles: SessionUser['role'][];
  children?: ReactNode;
}

export function RoleGate({ roles, children }: RoleGateProps) {
  const user = useSessionStore((state) => state.user);
  if (!user || !roles.includes(user.role)) {
    return <ForbiddenPage />;
  }
  return children ?? <Outlet />;
}

export function ForbiddenPage() {
  const { t } = useTranslation();
  return (
    <section className="py-10 text-center">
      <h1 className="text-xl font-semibold">{t('forbidden.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('forbidden.detail')}</p>
    </section>
  );
}

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <section className="py-10 text-center">
      <h1 className="text-xl font-semibold">{t('notFound.title')}</h1>
    </section>
  );
}
