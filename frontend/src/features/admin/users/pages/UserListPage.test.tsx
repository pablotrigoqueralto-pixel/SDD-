import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/store/session.store';
import { adminUser, page } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { UserListPage } from './UserListPage';

function renderList(route = '/admin/usuarios') {
  return renderRoutes(
    [
      { path: '/admin', element: <h1>Admin hub</h1> },
      {
        path: '/admin/usuarios',
        element: <UserListPage />,
        children: [
          { path: 'nuevo', element: <p>Nuevo form</p> },
          { path: ':userId', element: <p>Edit form</p> },
        ],
      },
    ],
    { route },
  );
}

describe('UserListPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', adminUser);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('lists users with Spanish role labels, territories and the inactive badge', async () => {
    server.use(
      http.get(`${API_V1}/users`, () =>
        HttpResponse.json(
          page([
            adminUser,
            {
              ...adminUser,
              id: 'u2',
              full_name: 'Bea Baja',
              email: 'bea@quermed.com',
              role: 'sales_rep',
              is_active: false,
              territory_ids: ['019000000-0000-7000-8000-0000000000a1'],
            },
          ]),
        ),
      ),
    );
    renderList();

    expect(await screen.findByText('Alicia Admin')).toBeInTheDocument();
    const list = screen.getByRole('list');
    expect(within(list).getByText('Administrador/a')).toBeInTheDocument();
    expect(within(list).getByText('Comercial')).toBeInTheDocument();
    expect(await within(list).findByText('Centro')).toBeInTheDocument();
    const bea = screen.getByText('Bea Baja').closest('li');
    expect(within(bea!).getByText('Inactivo')).toBeInTheDocument();
  });

  it('applies search and filters through the URL and calls the API with them', async () => {
    const user = userEvent.setup();
    const searches: string[] = [];
    server.use(
      http.get(`${API_V1}/users`, ({ request }) => {
        searches.push(new URL(request.url).search);
        return HttpResponse.json(page([adminUser]));
      }),
    );
    renderList();
    await screen.findByText('Alicia Admin');

    await user.selectOptions(screen.getByLabelText('Rol'), 'sales_manager');
    await user.selectOptions(screen.getByLabelText('Estado'), 'false');
    await user.type(screen.getByLabelText('Buscar'), 'al');

    await waitFor(() => {
      expect(searches.at(-1)).toBe('?q=al&role=sales_manager&is_active=false');
    });
  });

  it('shows the empty state with the create action and navigates to the form', async () => {
    const user = userEvent.setup();
    server.use(http.get(`${API_V1}/users`, () => HttpResponse.json(page([]))));
    renderList();

    expect(await screen.findByText('No hay usuarios que coincidan')).toBeInTheDocument();
    const buttons = screen.getAllByRole('button', { name: 'Nuevo usuario' });
    await user.click(buttons[buttons.length - 1]!);

    expect(await screen.findByText('Nuevo form')).toBeInTheDocument();
  });

  it('opens the edit form when a user card is selected', async () => {
    const user = userEvent.setup();
    renderList();

    await user.click(await screen.findByRole('button', { name: /Ana García/ }));

    expect(await screen.findByText('Edit form')).toBeInTheDocument();
  });
});
