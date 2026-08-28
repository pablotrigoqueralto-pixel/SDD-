import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/features/auth';
import { callPlanned, overdueVisit, today } from '@/test/msw/activities-fixtures';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { TodayNewRoute } from './pages/ActivityRoutes';
import { TodayPage } from './pages/TodayPage';

function renderToday(route = '/hoy') {
  return renderRoutes(
    [
      {
        path: '/hoy',
        element: <TodayPage />,
        children: [{ path: 'nueva', element: <TodayNewRoute /> }],
      },
      { path: '/centros/:accountId', element: <h1>Detalle</h1> },
    ],
    { route },
  );
}

describe('TodayPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('shows the weekly summary, overdue and planned lists with one-tap actions', async () => {
    renderToday();

    expect(await screen.findByText(/3 visita · 2 llamada · 4 pendientes/)).toBeInTheDocument();
    const overdue = screen.getByRole('region', { name: 'Atrasadas (1)' });
    expect(within(overdue).getByText('Clínica Tambre')).toBeInTheDocument();
    const planned = screen.getByRole('region', { name: 'Hoy (1)' });
    expect(within(planned).getByText('Seguimiento demo')).toBeInTheDocument();
    expect(within(planned).getByRole('button', { name: 'Hecha' })).toBeInTheDocument();
    expect(within(planned).getByRole('button', { name: 'Reprogramar' })).toBeInTheDocument();
    expect(within(planned).queryByRole('button', { name: 'Cancelar actividad' })).toBeNull();
    expect(screen.queryByRole('combobox', { name: 'Comercial' })).not.toBeInTheDocument();
  });

  it('completes from the compact sheet and reschedules an overdue activity', async () => {
    const user = userEvent.setup();
    const calls: { path: string; ifMatch: string | null; body: Record<string, unknown> }[] = [];
    server.use(
      http.post(`${API_V1}/activities/:id/complete`, async ({ request }) => {
        calls.push({
          path: new URL(request.url).pathname,
          ifMatch: request.headers.get('if-match'),
          body: (await request.json()) as Record<string, unknown>,
        });
        return HttpResponse.json({ ...callPlanned, status: 'done', version: 2 });
      }),
      http.post(`${API_V1}/activities/:id/reschedule`, async ({ request }) => {
        calls.push({
          path: new URL(request.url).pathname,
          ifMatch: request.headers.get('if-match'),
          body: (await request.json()) as Record<string, unknown>,
        });
        return HttpResponse.json({ ...overdueVisit, version: 2 });
      }),
    );
    renderToday();

    const planned = await screen.findByRole('region', { name: 'Hoy (1)' });
    await user.click(within(planned).getByRole('button', { name: 'Hecha' }));
    const sheet = await screen.findByRole('dialog');
    await user.selectOptions(
      within(sheet).getByRole('combobox', { name: 'Resultado' }),
      'Positiva',
    );
    await user.click(within(sheet).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    expect(calls[0]?.path.endsWith(`/${callPlanned.id}/complete`)).toBe(true);
    expect(calls[0]?.ifMatch).toBe('"1"');
    expect(calls[0]?.body).toMatchObject({ outcome: 'positive', next_action: null });

    const overdue = screen.getByRole('region', { name: 'Atrasadas (1)' });
    await user.click(within(overdue).getByRole('button', { name: 'Reprogramar' }));
    const resched = await screen.findByRole('dialog');
    const when = within(resched).getByLabelText('Nueva fecha y hora');
    await user.clear(when);
    await user.type(when, '2030-02-01T10:00');
    await user.click(within(resched).getByRole('button', { name: 'Guardar' }));
    await waitFor(() => {
      expect(calls).toHaveLength(2);
    });
    expect(calls[1]?.path.endsWith(`/${overdueVisit.id}/reschedule`)).toBe(true);
    expect(String(calls[1]?.body.scheduled_at)).toContain('2030-02-01');
  });

  it('shows empty states and lets a manager switch the rep; back office has no actions', async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    server.use(
      http.get(`${API_V1}/me/today`, ({ request }) => {
        seen.push(new URL(request.url).searchParams.get('user_id') ?? 'me');
        return HttpResponse.json({ ...today, today: [], overdue: [] });
      }),
    );
    sessionStore.getState().setSession('token', { ...adminUser, role: 'sales_manager' });
    const first = renderToday();

    expect(await screen.findByText('Nada planificado para hoy')).toBeInTheDocument();
    expect(screen.getByText('Sin actividades atrasadas')).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Comercial' }), 'Ana García');
    await waitFor(() => {
      expect(seen).toContain(repUser.id);
    });
    first.unmount();

    sessionStore.getState().setSession('token', { ...adminUser, role: 'back_office' });
    server.resetHandlers();
    renderToday();
    await screen.findByRole('region', { name: 'Hoy (1)' });
    expect(screen.queryByRole('button', { name: 'Nueva actividad' })).not.toBeInTheDocument();
  });

  it('keeps the scope warning and opens the account search from "Nueva actividad"', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', { ...repUser, division_ids: [] });
    renderToday();

    expect(await screen.findByRole('note')).toHaveTextContent(
      'Sin territorio o división asignados; contacta con administración',
    );
    await user.click(screen.getByRole('button', { name: 'Nueva actividad' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('searchbox', { name: 'Buscar centro' }), 'tam');
    await user.click(await within(dialog).findByRole('button', { name: 'Clínica Tambre' }));
    expect(await within(dialog).findByRole('radio', { name: 'Visita' })).toBeInTheDocument();
    expect(within(dialog).getByText('Clínica Tambre')).toBeInTheDocument();
  });
});
