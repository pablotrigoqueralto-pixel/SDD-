import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';

import { SplashScreen } from '@/components/shared/SplashScreen';

import { AuthGuard, NotFoundPage, RoleGate } from './guards';
import { AppShell } from './layout/AppShell';
import { MorePage } from './pages/MorePage';
import { routes } from './routes';

const LoginPage = lazy(() => import('@/features/auth').then((m) => ({ default: m.LoginPage })));
const AdminRoutes = lazy(() =>
  import('@/features/admin').then((m) => ({ default: m.AdminRoutes })),
);
const AccountRoutes = lazy(() =>
  import('@/features/accounts').then((m) => ({ default: m.AccountRoutes })),
);
const TodayPage = lazy(() =>
  import('@/features/activities').then((m) => ({ default: m.TodayPage })),
);
const TodayNewRoute = lazy(() =>
  import('@/features/activities').then((m) => ({ default: m.TodayNewRoute })),
);

function withSuspense(element: React.ReactNode) {
  return <Suspense fallback={<SplashScreen />}>{element}</Suspense>;
}

export const routeObjects: RouteObject[] = [
  { path: routes.login, element: withSuspense(<LoginPage />) },
  {
    element: <AuthGuard />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to={routes.today} replace /> },
          {
            path: routes.today,
            element: withSuspense(<TodayPage />),
            children: [{ path: 'nueva', element: withSuspense(<TodayNewRoute />) }],
          },
          { path: routes.more, element: <MorePage /> },
          { path: `${routes.accounts}/*`, element: withSuspense(<AccountRoutes />) },
          {
            path: `${routes.admin}/*`,
            element: <RoleGate roles={['admin']}>{withSuspense(<AdminRoutes />)}</RoleGate>,
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(routeObjects);
}
