import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { MorePage } from '@/app/pages/MorePage';
import { sessionStore } from '@/store/session.store';
import { adminUser, problem } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { bootstrapSession } from './bootstrap';

describe('bootstrapSession', () => {
  beforeEach(() => {
    sessionStore.setState({ status: 'unknown', accessToken: null, user: null });
  });

  it('restores the session from the refresh cookie', async () => {
    await bootstrapSession();

    expect(sessionStore.getState().status).toBe('authenticated');
    expect(sessionStore.getState().accessToken).toBe('access-token-refreshed');
    expect(sessionStore.getState().user?.id).toBe(adminUser.id);
  });

  it('marks the session anonymous when the refresh fails', async () => {
    server.use(http.post(`${API_V1}/auth/refresh`, () => problem(401, 'unauthenticated', 'no')));

    await bootstrapSession();

    expect(sessionStore.getState().status).toBe('anonymous');
  });

  it('does nothing when the session is already known', async () => {
    sessionStore.getState().clear();
    let calls = 0;
    server.use(
      http.post(`${API_V1}/auth/refresh`, () => {
        calls += 1;
        return problem(401, 'unauthenticated', 'no');
      }),
    );

    await bootstrapSession();

    expect(calls).toBe(0);
  });
});

describe('logout', () => {
  it('clears the session and the query cache, then navigates to /login', async () => {
    sessionStore.getState().setSession('token', adminUser);
    const user = userEvent.setup();
    const { queryClient } = renderRoutes(
      [
        { path: '/mas', element: <MorePage /> },
        { path: '/login', element: <h1>Login page</h1> },
      ],
      { route: '/mas' },
    );
    queryClient.setQueryData(['users', 'list'], { items: [] });

    await user.click(screen.getByRole('button', { name: 'Cerrar sesión' }));

    expect(await screen.findByText('Login page')).toBeInTheDocument();
    expect(sessionStore.getState().status).toBe('anonymous');
    expect(queryClient.getQueryData(['users', 'list'])).toBeUndefined();
  });
});
