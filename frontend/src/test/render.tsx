import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter, useRoutes, type RouteObject } from 'react-router-dom';

import { i18n } from '@/i18n';

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface Options extends Omit<RenderOptions, 'wrapper'> {
  route?: string;
  queryClient?: QueryClient;
}

type Result = RenderResult & { queryClient: QueryClient };

function RouteTree({ routes }: { routes: RouteObject[] }): ReactElement | null {
  return useRoutes(routes);
}

/**
 * Tests use the non-data MemoryRouter: the data router builds `Request` objects on every
 * navigation, which jsdom + MSW cannot construct. Route trees are identical otherwise.
 */
function renderRouter(
  routes: RouteObject[],
  { route = '/', queryClient = createTestQueryClient(), ...options }: Options,
): Result {
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </I18nextProvider>
      </QueryClientProvider>
    );
  }

  const result = render(<RouteTree routes={routes} />, { wrapper: Wrapper, ...options });
  return { ...result, queryClient };
}

/** Render one element with the real providers (Query, Router, i18n). */
export function renderWithProviders(ui: ReactElement, options: Options = {}): Result {
  return renderRouter([{ path: '*', element: ui }], options);
}

/** Render a route tree (for pages that navigate, guard or redirect). */
export function renderRoutes(routes: RouteObject[], options: Options = {}): Result {
  return renderRouter(routes, options);
}
