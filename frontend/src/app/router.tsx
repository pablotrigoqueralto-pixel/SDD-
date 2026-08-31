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
const OpportunityRoutes = lazy(() =>
  import('@/features/opportunities').then((m) => ({ default: m.OpportunityRoutes })),
);
const CatalogueRoutes = lazy(() =>
  import('@/features/catalogue').then((m) => ({ default: m.CatalogueRoutes })),
);
const QuoteRoutes = lazy(() =>
  import('@/features/quotes').then((m) => ({ default: m.QuoteRoutes })),
);
const ContactListPage = lazy(() =>
  import('@/features/contacts').then((m) => ({ default: m.ContactListPage })),
);
const SearchPage = lazy(() => import('@/features/search').then((m) => ({ default: m.SearchPage })));
const InformesPage = lazy(() =>
  import('@/features/dashboard').then((m) => ({ default: m.InformesPage })),
);
const ImportCataloguePage = lazy(() =>
  import('@/features/imports').then((m) => ({ default: m.ImportCataloguePage })),
);
const ImportAccountsPage = lazy(() =>
  import('@/features/imports').then((m) => ({ default: m.ImportAccountsPage })),
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
          { path: `${routes.catalogue}/*`, element: withSuspense(<CatalogueRoutes />) },
          { path: `${routes.quotes}/*`, element: withSuspense(<QuoteRoutes />) },
          { path: routes.contacts, element: withSuspense(<ContactListPage />) },
          { path: routes.search, element: withSuspense(<SearchPage />) },
          { path: routes.reports, element: withSuspense(<InformesPage />) },
          {
            path: routes.importCatalogue,
            element: (
              <RoleGate roles={['admin', 'back_office']}>
                {withSuspense(<ImportCataloguePage />)}
              </RoleGate>
            ),
          },
          {
            path: routes.importAccounts,
            element: (
              <RoleGate roles={['admin', 'back_office']}>
                {withSuspense(<ImportAccountsPage />)}
              </RoleGate>
            ),
          },
          {
            path: `${routes.opportunities}/*`,
            element: withSuspense(<OpportunityRoutes />),
          },
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
