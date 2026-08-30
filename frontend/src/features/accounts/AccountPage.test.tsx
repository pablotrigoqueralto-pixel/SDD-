import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { laPaz, tambre } from '@/test/msw/accounts-fixtures';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { AccountDialogRoute } from './pages/AccountFormRoute';
import { AccountPage } from './pages/AccountPage';

function renderPage(route: string) {
  return renderRoutes(
    [
      { path: '/centros', element: <h1>Centros</h1> },
      {
        path: '/centros/:accountId',
        element: <AccountPage />,
        children: [
          { path: 'editar', element: <h1>Editar</h1> },
          { path: 'direcciones', element: <AccountDialogRoute kind="addresses" /> },
          { path: 'asignar', element: <AccountDialogRoute kind="assign" /> },
          { path: 'contactos/nuevo', element: <h1>Nuevo contacto</h1> },
        ],
      },
    ],
    { route },
  );
}

describe('AccountPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('renders the header, the sections in order and the placeholders without requests', async () => {
    const requested: string[] = [];
    server.events.on('request:start', ({ request }) => {
      requested.push(new URL(request.url).pathname);
    });
    renderPage(`/centros/${tambre.id}`);

    expect(await screen.findByRole('heading', { name: 'Clínica Tambre' })).toBeInTheDocument();
    expect(screen.getByText(/Territorio: Centro · Comercial: Ana García/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Contactos (2)' }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Disponible en una próxima versión')).toHaveLength(2); // 1 × 2 layouts
    expect(requested.filter((path) => path.includes('equipment'))).toEqual([]);
    expect(requested.some((path) => path.endsWith('/opportunities'))).toBe(true);
    expect(screen.queryByRole('button', { name: 'Reasignar' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Nuevo contacto' }).length).toBeGreaterThan(0);
  });

  it('lists contacts with call and mail links and a consent badge', async () => {
    renderPage(`/centros/${tambre.id}`);

    const ana = (await screen.findAllByRole('article'))[0]!;
    expect(ana).toHaveTextContent('Ana Pérez');
    expect(within(ana).getByText('Principal')).toBeInTheDocument();
    expect(within(ana).getByText('Concedido')).toBeInTheDocument();
    expect(within(ana).getByRole('link', { name: 'Llamar a Ana Pérez' })).toHaveAttribute(
      'href',
      'tel:+34612345678',
    );
    expect(within(ana).getByRole('link', { name: 'Escribir a Ana Pérez' })).toHaveAttribute(
      'href',
      'mailto:ana@tambre.es',
    );
    expect(await within(ana).findByText('Ginecólogo/a · Vascular')).toBeInTheDocument();
  });

  it('remembers collapsed sections in localStorage', async () => {
    const user = userEvent.setup();
    const first = renderPage(`/centros/${tambre.id}`);
    await screen.findByRole('heading', { name: 'Clínica Tambre' });

    const dataButtons = screen.getAllByRole('button', { name: 'Datos' });
    await user.click(dataButtons[0]!);
    expect(dataButtons[0]).toHaveAttribute('aria-expanded', 'false');
    first.unmount();

    renderPage(`/centros/${tambre.id}`);
    await screen.findByRole('heading', { name: 'Clínica Tambre' });
    expect(screen.getAllByRole('button', { name: 'Datos' })[0]).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  });

  it('shows "Centro no encontrado" on 404 with a link back', async () => {
    renderPage('/centros/unknown');

    expect(
      await screen.findByRole('heading', { name: 'Centro no encontrado' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver a Centros' })).toHaveAttribute(
      'href',
      '/centros',
    );
  });

  it('lets a manager reassign and anonymise', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', { ...adminUser, role: 'sales_manager' });
    let assignment: Record<string, unknown> = {};
    let anonymised = false;
    server.use(
      http.put(`${API_V1}/accounts/:id/assignment`, async ({ request }) => {
        assignment = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...laPaz, owner_id: repUser.id, owner_name: 'Ana García' });
      }),
      http.post(`${API_V1}/contacts/:id/anonymise`, () => {
        anonymised = true;
        return HttpResponse.json({ ...tambre, first_name: 'Contacto' });
      }),
    );
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage(`/centros/${laPaz.id}`);

    await user.click(await screen.findByRole('button', { name: 'Reasignar' }));
    const dialog = await screen.findByRole('dialog');
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Comercial' }),
      'Ana García',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => {
      expect(assignment).toEqual({ owner_id: repUser.id, territory_id: laPaz.territory_id });
    });

    renderPage(`/centros/${tambre.id}`);
    const anonymiseButtons = await screen.findAllByRole('button', { name: 'Anonimizar' });
    await user.click(anonymiseButtons[0]!);
    await waitFor(() => {
      expect(anonymised).toBe(true);
    });
  });

  it('edits the additional addresses with label uniqueness', async () => {
    const user = userEvent.setup();
    let body: { addresses: { label: string }[] } | null = null;
    let ifMatch: string | null = null;
    server.use(
      http.put(`${API_V1}/accounts/:id/addresses`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as { addresses: { label: string }[] };
        return HttpResponse.json({ ...tambre, version: 4 });
      }),
    );
    renderPage(`/centros/${tambre.id}/direcciones`);

    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Añadir dirección' }));
    const labels = within(dialog).getAllByLabelText('Etiqueta');
    await user.type(labels[1]!, 'laboratorio');
    await user.type(within(dialog).getAllByLabelText('Dirección')[1]!, 'Calle 2');
    await user.type(within(dialog).getAllByLabelText('Código postal')[1]!, '28003');
    await user.type(within(dialog).getAllByLabelText('Ciudad')[1]!, 'Madrid');
    await user.selectOptions(
      within(dialog).getAllByRole('combobox', { name: 'Provincia' })[1]!,
      'Madrid',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    expect(
      await within(dialog).findByText('Hay dos direcciones con la misma etiqueta'),
    ).toBeInTheDocument();

    await user.clear(labels[1]!);
    await user.type(labels[1]!, 'Almacén');
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => {
      expect(body?.addresses.map((a) => a.label)).toEqual(['Laboratorio', 'Almacén']);
    });
    expect(ifMatch).toBe('"3"');
  });
});
