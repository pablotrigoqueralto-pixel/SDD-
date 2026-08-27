import { screen } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/features/auth';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { renderRoutes } from '@/test/render';

import { AuthGuard, RoleGate } from './guards';

function LocationEcho() {
  const location = useLocation();
  return <p>{`${location.pathname}${location.search}`}</p>;
}

function renderGuarded(route: string) {
  return renderRoutes(
    [
      { path: '/login', element: <LocationEcho /> },
      {
        element: <AuthGuard />,
        children: [
          { path: '/hoy', element: <h1>Hoy</h1> },
          {
            path: '/admin/usuarios',
            element: (
              <RoleGate roles={['admin']}>
                <h1>Usuarios</h1>
              </RoleGate>
            ),
          },
        ],
      },
    ],
    { route },
  );
}

describe('AuthGuard', () => {
  beforeEach(() => {
    sessionStore.setState({ status: 'unknown', accessToken: null, user: null });
  });

  it('shows the splash while the session is unknown', () => {
    renderGuarded('/hoy');

    expect(screen.getByRole('status', { name: 'Cargando…' })).toBeInTheDocument();
  });

  it('redirects anonymous users to /login preserving the intended url', async () => {
    sessionStore.getState().clear();
    renderGuarded('/admin/usuarios?page=2');

    expect(
      await screen.findByText('/login?next=%2Fadmin%2Fusuarios%3Fpage%3D2'),
    ).toBeInTheDocument();
  });

  it('renders the page for authenticated users', () => {
    sessionStore.getState().setSession('token', repUser);
    renderGuarded('/hoy');

    expect(screen.getByRole('heading', { name: 'Hoy' })).toBeInTheDocument();
  });
});

describe('RoleGate', () => {
  it('shows "Sin permiso" to a sales rep on an admin route', () => {
    sessionStore.getState().setSession('token', repUser);
    renderGuarded('/admin/usuarios');

    expect(screen.getByRole('heading', { name: 'Sin permiso' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Usuarios' })).not.toBeInTheDocument();
  });

  it('lets an admin through', () => {
    sessionStore.getState().setSession('token', adminUser);
    renderGuarded('/admin/usuarios');

    expect(screen.getByRole('heading', { name: 'Usuarios' })).toBeInTheDocument();
  });
});
