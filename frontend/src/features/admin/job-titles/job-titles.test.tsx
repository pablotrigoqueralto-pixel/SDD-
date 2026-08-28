import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { problem } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { jobTitles } from '@/test/msw/reference-fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { AdminHubPage } from '../pages/AdminHubPage';
import { JobTitleForm } from './components/JobTitleForm';
import { JobTitleFormRoute, JobTitleListPage } from './pages/JobTitleListPage';

function renderList(route = '/admin/cargos') {
  return renderRoutes(
    [
      { path: '/admin', element: <AdminHubPage /> },
      {
        path: '/admin/cargos',
        element: <JobTitleListPage />,
        children: [
          { path: 'nuevo', element: <JobTitleFormRoute /> },
          { path: ':jobTitleId', element: <JobTitleFormRoute /> },
        ],
      },
    ],
    { route },
  );
}

describe('job titles administration', () => {
  it('reaches the list from the hub card and shows inactive badges', async () => {
    const user = userEvent.setup();
    renderList('/admin');

    await user.click(screen.getByRole('link', { name: /Cargos/ }));

    const list = await screen.findByRole('list');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Ginecólogo/a');
    expect(within(items[2]!).getByText('Inactivo')).toBeInTheDocument();
  });

  it('creates a title and reports the duplicate under the field', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/job-titles`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        if (body.name === 'Gerencia') {
          return problem(409, 'job_title_name_already_exists', 'dup');
        }
        return HttpResponse.json(
          { ...jobTitles[0]!, id: 'created', name_es: body.name },
          { status: 201 },
        );
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<JobTitleForm onSaved={onSaved} />);

    await user.type(screen.getByLabelText('Nombre'), 'Gerencia');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Ya existe un cargo con este nombre')).toBeInTheDocument();

    await user.clear(screen.getByLabelText('Nombre'));
    await user.type(screen.getByLabelText('Nombre'), 'Farmacia hospitalaria');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({ name: 'Farmacia hospitalaria' });
  });

  it('renames and deactivates with the version from the list route', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    server.use(
      http.patch(`${API_V1}/job-titles/:id`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...jobTitles[1]!, name_es: body.name, version: 2 });
      }),
    );
    renderList();

    await user.click(await screen.findByRole('button', { name: /Compras/ }));
    const dialog = await screen.findByRole('dialog');
    await user.clear(within(dialog).getByLabelText('Nombre'));
    await user.type(within(dialog).getByLabelText('Nombre'), 'Compras');
    await user.click(within(dialog).getByLabelText('Activo'));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(body).toEqual({ name: 'Compras', is_active: false });
    });
    expect(ifMatch).toBe('"1"');
  });
});
