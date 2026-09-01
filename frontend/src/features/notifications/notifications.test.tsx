import { focusManager } from '@tanstack/react-query';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/features/auth';
import { API_V1 } from '@/test/msw/constants';
import { repUser } from '@/test/msw/fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { NotificationsBell } from './components/NotificationsBell';
import { NotificationsBlock } from './components/NotificationsBlock';

const ACCOUNT_ID = '019000000-0000-7000-8000-0000000000a1';

function inbox(count: number) {
  return {
    unread_count: count,
    items: Array.from({ length: count }, (_, index) => ({
      id: `notice-${index}`,
      kind: 'account_assigned' as const,
      entity_type: 'account',
      entity_id: ACCOUNT_ID,
      actor_id: 'manager',
      actor_name: 'Marta Jefa',
      payload: { account_name: 'Clínica Tambre' },
      created_at: '2026-09-01T10:00:00Z',
    })),
  };
}

describe('notifications', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('counts the unread ones in the accessible name of the bell', async () => {
    server.use(http.get(`${API_V1}/notifications`, () => HttpResponse.json(inbox(3))));

    renderWithProviders(<NotificationsBell />);

    expect(
      await screen.findByRole('button', { name: 'Notificaciones: 3 sin leer' }),
    ).toBeInTheDocument();
  });

  it('says there is nothing new instead of showing a bare dot', async () => {
    server.use(http.get(`${API_V1}/notifications`, () => HttpResponse.json(inbox(0))));

    renderWithProviders(<NotificationsBell />);

    expect(
      await screen.findByRole('button', { name: 'Notificaciones: nada nuevo' }),
    ).toBeInTheDocument();
  });

  it('lists what somebody else assigned and opens it, marking it read', async () => {
    const user = userEvent.setup();
    let readId: string | null = null;
    server.use(
      http.get(`${API_V1}/notifications`, () => HttpResponse.json(inbox(1))),
      http.post(`${API_V1}/notifications/:id/read`, ({ params }) => {
        readId = String(params.id);
        return HttpResponse.json(inbox(0));
      }),
    );
    renderRoutes(
      [
        { path: '/', element: <NotificationsBlock /> },
        { path: '/centros/:id', element: <h1>Ficha del centro</h1> },
      ],
      { route: '/' },
    );

    const list = await screen.findByRole('list', { name: 'Novedades' });
    expect(
      within(list).getByText(/Marta Jefa te ha asignado el centro Clínica Tambre/),
    ).toBeVisible();

    await user.click(within(list).getByRole('button'));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Ficha del centro' })).toBeInTheDocument();
    });
    expect(readId).toBe('notice-0');
  });

  it('clears the block with mark all, and renders nothing when empty', async () => {
    const user = userEvent.setup();
    let cleared = false;
    server.use(
      http.get(`${API_V1}/notifications`, () => HttpResponse.json(cleared ? inbox(0) : inbox(2))),
      http.post(`${API_V1}/notifications/read-all`, () => {
        cleared = true;
        return HttpResponse.json(inbox(0));
      }),
    );
    renderWithProviders(<NotificationsBlock />);

    await user.click(await screen.findByRole('button', { name: 'Marcar todo como leído' }));

    await waitFor(() => {
      expect(screen.queryByRole('list', { name: 'Novedades' })).not.toBeInTheDocument();
    });
    // An empty inbox is not news: no empty state either.
    expect(screen.queryByText('Novedades')).not.toBeInTheDocument();
  });

  it('refetches when the window regains focus, and not on a timer', async () => {
    let calls = 0;
    server.use(
      http.get(`${API_V1}/notifications`, () => {
        calls += 1;
        return HttpResponse.json(inbox(calls));
      }),
    );
    renderWithProviders(<NotificationsBell />);
    await screen.findByRole('button', { name: 'Notificaciones: 1 sin leer' });

    // Coming back to the tab is the moment that matters, not a badge ticking unwatched.
    // Drive the query client's own focus manager: jsdom never really loses focus.
    focusManager.setFocused(false);
    focusManager.setFocused(true);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Notificaciones: 2 sin leer' })).toBeVisible();
    });
  });
});
