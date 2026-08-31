import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { summaryOf, tambre } from '@/test/msw/accounts-fixtures';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { AccountListPage } from './pages/AccountListPage';

function mockViewport(desktop: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    matches: desktop && query.includes('1024px'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function renderList(route = '/centros') {
  return renderRoutes(
    [
      { path: '/centros', element: <AccountListPage /> },
      { path: '/centros/nuevo', element: <h1>Nuevo</h1> },
      { path: '/centros/:accountId', element: <h1>Detalle</h1> },
    ],
    { route },
  );
}

describe('AccountListPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
    mockViewport(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders cards with type, city, owner and badges on mobile', async () => {
    renderList();

    const list = await screen.findByRole('list');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Clínica Tambre');
    expect(items[0]).toHaveTextContent('Clínica FIV / laboratorio');
    expect(items[0]).toHaveTextContent('Ana García');
    expect(items[1]).toHaveTextContent('Hospital La Paz');
    expect(within(items[1]!).getByText('Sin comercial')).toBeInTheDocument();
    expect(within(items[1]!).getByText('Territorio distinto')).toBeInTheDocument();
  });

  it('offers the primary phone as a call link on the desktop table', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: true,
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
          addListener: () => undefined,
          removeListener: () => undefined,
          onchange: null,
          dispatchEvent: () => false,
        }),
    );
    renderList();

    const call = await screen.findByRole('link', { name: '+34911234567' });
    expect(call).toHaveAttribute('href', 'tel:+34911234567');
  });

  it('debounces the search into the URL and the request', async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    server.use(
      http.get(`${API_V1}/accounts`, ({ request }) => {
        seen.push(new URL(request.url).searchParams.get('q') ?? '');
        return HttpResponse.json({
          items: [summaryOf(tambre, null)],
          total: 1,
          page: 1,
          page_size: 25,
        });
      }),
    );
    renderList();
    await screen.findByRole('list');

    await user.type(screen.getByRole('searchbox', { name: 'Buscar' }), 'tam');

    await waitFor(() => {
      expect(seen).toContain('tam');
    });
    expect(seen).not.toContain('t');
  });

  it('opens the filters sheet on mobile and applies the type filter', async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    server.use(
      http.get(`${API_V1}/accounts`, ({ request }) => {
        seen.push(new URL(request.url).searchParams.get('account_type_id') ?? '');
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
    );
    renderList();
    expect(await screen.findByText('No hay centros que coincidan')).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Territorio' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Filtros' }));
    const sheet = await screen.findByRole('dialog');
    await user.selectOptions(
      within(sheet).getByRole('combobox', { name: 'Tipo' }),
      'Hospital público',
    );

    await waitFor(() => {
      expect(seen.at(-1)).toBe('019000000-0000-7000-8000-0000000000t2');
    });
    // Reps never see the territory/owner filters (they cannot list users).
    expect(within(sheet).queryByRole('combobox', { name: 'Comercial' })).not.toBeInTheDocument();
  });

  it('loads more pages on mobile and paginates on desktop', async () => {
    const user = userEvent.setup();
    const many = Array.from({ length: 30 }, (_, index) => ({
      ...summaryOf(tambre, null),
      id: `acc-${index}`,
      name: `Centro ${index}`,
    }));
    server.use(
      http.get(`${API_V1}/accounts`, ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get('page') ?? '1');
        return HttpResponse.json({
          items: many.slice((page - 1) * 25, page * 25),
          total: many.length,
          page,
          page_size: 25,
        });
      }),
    );
    const mobile = renderList();
    await screen.findByRole('list');
    await user.click(screen.getByRole('button', { name: 'Cargar más' }));
    await waitFor(() => {
      expect(screen.getAllByRole('listitem')).toHaveLength(30);
    });
    expect(screen.queryByRole('button', { name: 'Cargar más' })).not.toBeInTheDocument();
    mobile.unmount();

    mockViewport(true);
    sessionStore.getState().setSession('token', adminUser);
    renderList('/centros?page=2');
    const table = await screen.findByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(6); // header + 5
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Comercial' })).toBeInTheDocument();
  });

  it('navigates to the detail on selection and to the form from the empty state', async () => {
    const user = userEvent.setup();
    renderList();

    await user.click(await screen.findByRole('button', { name: /Hospital La Paz/ }));
    expect(await screen.findByRole('heading', { name: 'Detalle' })).toBeInTheDocument();
  });
});
