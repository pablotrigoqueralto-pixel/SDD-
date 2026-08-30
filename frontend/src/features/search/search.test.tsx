import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { navigationFor } from '@/app/layout/navigation';
import { MorePage } from '@/app/pages/MorePage';
import { sessionStore } from '@/features/auth';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { emptySearchResults } from '@/test/msw/handlers/search-imports';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { SearchPage } from './pages/SearchPage';
import { recentRecords, rememberRecord, rememberSearch } from './recents';

function renderSearch() {
  return renderRoutes(
    [
      { path: '/buscar', element: <SearchPage /> },
      { path: '/centros', element: <h1>Lista centros</h1> },
      { path: '/centros/:accountId', element: <h1>Centro detalle</h1> },
      { path: '/presupuestos/:quoteId', element: <h1>Presupuesto detalle</h1> },
    ],
    { route: '/buscar' },
  );
}

describe('SearchPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
    window.localStorage.clear();
  });

  it('debounces to one request and renders grouped results with see-all links', async () => {
    const user = userEvent.setup();
    const queries: string[] = [];
    server.use(
      http.get(`${API_V1}/search`, ({ request }) => {
        const q = new URL(request.url).searchParams.get('q') ?? '';
        queries.push(q);
        return HttpResponse.json({
          ...emptySearchResults(q),
          accounts: {
            items: [
              {
                id: 'acc-1',
                name: 'Clínica Tambre',
                city: 'Madrid',
                province_code: '28',
                is_active: true,
              },
            ],
            total: 7,
            has_more: true,
          },
        });
      }),
    );
    renderSearch();

    await user.type(screen.getByRole('searchbox', { name: 'Buscar' }), 'tambre');
    expect(await screen.findByText('Clínica Tambre')).toBeInTheDocument();
    expect(queries).toEqual(['tambre']); // one request after the debounce

    const seeAll = screen.getByRole('link', { name: 'Ver todas' });
    expect(seeAll).toHaveAttribute('href', '/centros?q=tambre');
  });

  it('navigates on row tap and remembers the record', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByRole('searchbox', { name: 'Buscar' }), 'tambre');
    await user.click(await screen.findByRole('button', { name: /P-2026-0002/ }));

    expect(await screen.findByText('Presupuesto detalle')).toBeInTheDocument();
    expect(recentRecords()[0]).toMatchObject({ kind: 'quote', label: 'P-2026-0002' });
  });

  it('shows recents before typing and survives a failing localStorage', () => {
    rememberSearch('doppler');
    rememberRecord({ kind: 'account', id: 'acc-9', label: 'Clínica Guardada' });
    renderSearch();

    expect(screen.getByText('Búsquedas recientes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /doppler/ })).toBeInTheDocument();
    expect(screen.getByText('Clínica Guardada')).toBeInTheDocument();

    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    try {
      expect(recentRecords()).toEqual([]);
    } finally {
      spy.mockRestore();
    }
  });

  it('shows the empty state when nothing matches', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API_V1}/search`, ({ request }) =>
        HttpResponse.json(emptySearchResults(new URL(request.url).searchParams.get('q') ?? '')),
      ),
    );
    renderSearch();

    await user.type(screen.getByRole('searchbox', { name: 'Buscar' }), 'nada');
    expect(await screen.findByText(/Sin resultados para/)).toBeInTheDocument();
  });
});

describe('Navigation swap', () => {
  it('shows Buscar in the fifth-slot bar for every role', () => {
    const keys = navigationFor(repUser).map((entry) => entry.key);
    expect(keys).toEqual(['today', 'accounts', 'pipeline', 'search', 'more']);
    expect(navigationFor(adminUser).map((entry) => entry.key)).toEqual(keys);
  });

  it('offers Administración as the first card in Más for admins only', async () => {
    sessionStore.getState().setSession('token', adminUser);
    const admin = renderWithProviders(<MorePage />);
    const links = await screen.findAllByRole('link');
    expect(links[0]).toHaveTextContent('Administración');
    expect(screen.getByText('Importar catálogo')).toBeInTheDocument();
    admin.unmount();

    sessionStore.getState().setSession('token', repUser);
    renderWithProviders(<MorePage />);
    await waitFor(() => {
      expect(screen.queryByText('Administración')).not.toBeInTheDocument();
    });
    expect(screen.queryByText('Importar catálogo')).not.toBeInTheDocument();
  });
});
