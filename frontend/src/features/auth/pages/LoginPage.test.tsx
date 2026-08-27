import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/store/session.store';
import { problem } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { LoginPage } from './LoginPage';

function renderLogin(route = '/login') {
  return renderRoutes(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/hoy', element: <h1>Hoy page</h1> },
      { path: '/admin/usuarios', element: <h1>Usuarios page</h1> },
    ],
    { route },
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    sessionStore.getState().clear();
  });

  it('logs in and navigates to /hoy by default', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'admin@quermed.com');
    await user.type(screen.getByLabelText('Contraseña'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByText('Hoy page')).toBeInTheDocument();
    expect(sessionStore.getState().accessToken).toBe('access-token-admin');
    expect(sessionStore.getState().user?.email).toBe('admin@quermed.com');
  });

  it('honours the next parameter and submits with Enter', async () => {
    const user = userEvent.setup();
    renderLogin('/login?next=%2Fadmin%2Fusuarios');

    await user.type(screen.getByLabelText('Email'), 'admin@quermed.com');
    await user.type(screen.getByLabelText('Contraseña'), 'correct-horse-battery{enter}');

    expect(await screen.findByText('Usuarios page')).toBeInTheDocument();
  });

  it('shows the invalid credentials message and keeps the email', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'admin@quermed.com');
    await user.type(screen.getByLabelText('Contraseña'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Email o contraseña incorrectos');
    expect(screen.getByLabelText('Email')).toHaveValue('admin@quermed.com');
    expect(screen.getByLabelText('Contraseña')).toHaveValue('');
  });

  it('shows the locked account message', async () => {
    server.use(http.post(`${API_V1}/auth/login`, () => problem(401, 'account_locked', 'locked')));
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'admin@quermed.com');
    await user.type(screen.getByLabelText('Contraseña'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Cuenta bloqueada temporalmente. Inténtalo en 15 minutos',
    );
  });

  it('validates required fields without calling the API', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByText('Introduce tu email')).toBeInTheDocument();
    expect(screen.getByText('Introduce tu contraseña')).toBeInTheDocument();
  });

  it('keeps the tab order email → password → submit', () => {
    renderLogin();

    const email = screen.getByLabelText('Email');
    const password = screen.getByLabelText('Contraseña');
    const submit = screen.getByRole('button', { name: 'Entrar' });
    expect(email.compareDocumentPosition(password) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(
      password.compareDocumentPosition(submit) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('redirects an already authenticated user', async () => {
    sessionStore.getState().setSession('token', {
      id: '1',
      email: 'a@quermed.com',
      full_name: 'A',
      role: 'sales_rep',
      is_active: true,
      identity_provider: 'password',
      territory_ids: [],
      division_ids: [],
      version: 1,
      created_at: null,
      updated_at: null,
    });
    renderLogin();

    await waitFor(() => {
      expect(screen.getByText('Hoy page')).toBeInTheDocument();
    });
  });
});
