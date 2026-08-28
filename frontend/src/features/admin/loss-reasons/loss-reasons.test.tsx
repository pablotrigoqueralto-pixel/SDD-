import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { problem } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { lossReasons } from '@/test/msw/reference-fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { LossReasonForm } from './components/LossReasonForm';
import { LossReasonFormRoute, LossReasonListPage } from './pages/LossReasonListPage';

function renderList(route = '/admin/motivos-perdida') {
  return renderRoutes(
    [
      { path: '/admin', element: <h1>Hub</h1> },
      {
        path: '/admin/motivos-perdida',
        element: <LossReasonListPage />,
        children: [
          { path: 'nuevo', element: <LossReasonFormRoute /> },
          { path: ':reasonId', element: <LossReasonFormRoute /> },
        ],
      },
    ],
    { route },
  );
}

describe('LossReasonListPage', () => {
  it('lists reasons in order with requirement badges', async () => {
    renderList();

    const list = await screen.findByRole('list');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Precio');
    expect(items[1]).toHaveTextContent('Competidor');
    expect(within(items[1]!).getByText('Requiere marca')).toBeInTheDocument();
    expect(within(items[2]!).getByText('Requiere nota')).toBeInTheDocument();
  });

  it('opens the edit form with read-only requirement badges', async () => {
    const user = userEvent.setup();
    renderList();

    await user.click(await screen.findByRole('button', { name: /Competidor/ }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText('Nombre')).toHaveValue('Competidor');
    expect(within(dialog).getByText('Requiere marca')).toBeInTheDocument();
    expect(within(dialog).queryByLabelText('Requiere marca')).not.toBeInTheDocument();
  });
});

describe('LossReasonForm', () => {
  it('creates a reason and reports the duplicate error under the field', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/loss-reasons`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        if (body.name === 'Precio') {
          return problem(409, 'loss_reason_name_already_exists', 'dup');
        }
        return HttpResponse.json(
          { ...lossReasons[0]!, id: 'created', name_es: body.name },
          { status: 201 },
        );
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<LossReasonForm onSaved={onSaved} />);

    await user.type(screen.getByLabelText('Nombre'), 'Precio');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Ya existe un motivo con este nombre')).toBeInTheDocument();

    await user.clear(screen.getByLabelText('Nombre'));
    await user.type(screen.getByLabelText('Nombre'), 'Cambio de proveedor');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({ name: 'Cambio de proveedor' });
  });

  it('edits name and active flag with the version', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    server.use(
      http.patch(`${API_V1}/loss-reasons/:id`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...lossReasons[0]!, ...body, version: 2 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<LossReasonForm reason={lossReasons[0]!} onSaved={onSaved} />);

    await user.clear(screen.getByLabelText('Nombre'));
    await user.type(screen.getByLabelText('Nombre'), 'Precio alto');
    await user.click(screen.getByLabelText('Activo'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(ifMatch).toBe('"1"');
    expect(body).toEqual({ name: 'Precio alto', is_active: false });
  });
});
