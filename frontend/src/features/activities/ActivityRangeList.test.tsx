import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/features/auth';
import { API_V1 } from '@/test/msw/constants';
import { adminUser, problem, repUser } from '@/test/msw/fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { ActivityRangeList } from './components/ActivityRangeList';
import { TodayPage } from './pages/TodayPage';

const ENTRY = {
  id: 'entry-1',
  occurred_on: '2026-09-03',
  occurred_time: '09:30',
  status: 'planned' as const,
  activity_type: { code: 'visit', name: 'Visita', icon: 'building' },
  account_id: '019000000-0000-7000-8000-0000000000a1',
  account_name: 'Clínica Tambre',
  owner_id: '019000000-0000-7000-8000-0000000000r2',
  owner_name: 'Bruno Pérez',
  is_attendee: false,
};

function renderList() {
  return renderRoutes(
    [
      { path: '/hoy', element: <ActivityRangeList /> },
      { path: '/centros/:id', element: <h1>Detalle</h1> },
    ],
    { route: '/hoy' },
  );
}

describe('ActivityRangeList', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', adminUser);
  });

  it('asks for the current month and lists what came back', async () => {
    const asked: string[] = [];
    server.use(
      http.get(`${API_V1}/activities/calendar`, ({ request }) => {
        asked.push(new URL(request.url).search);
        return HttpResponse.json({ total: 1, items: [ENTRY], from_date: null, to_date: null });
      }),
    );
    renderList();

    const list = await screen.findByRole('list', { name: 'Listado' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(1);
    expect(within(list).getAllByText(/Clínica Tambre/).length).toBeGreaterThan(0);
    expect(asked[0]).toContain('from=');
    expect(asked[0]).toContain('to=');
  });

  it('narrows to one rep for staff and hides the selector from a rep', async () => {
    const user = userEvent.setup();
    const asked: string[] = [];
    server.use(
      http.get(`${API_V1}/activities/calendar`, ({ request }) => {
        asked.push(new URL(request.url).search);
        return HttpResponse.json({ total: 0, items: [] });
      }),
    );
    renderList();

    await screen.findByRole('option', { name: 'Bruno Pérez' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Comercial' }), 'Bruno Pérez');
    await waitFor(() => {
      expect(asked.at(-1)).toContain('owner_id=');
    });
    expect(await screen.findByText('Sin actividades en estas fechas')).toBeInTheDocument();
  });

  it('gives a rep no selector: the list is their own', async () => {
    sessionStore.getState().setSession('token', repUser);
    server.use(
      http.get(`${API_V1}/activities/calendar`, () => HttpResponse.json({ total: 0, items: [] })),
    );

    renderList();

    expect(await screen.findByLabelText('Desde')).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Comercial' })).toBeNull();
  });

  it('shows the backend refusal when the range is too long', async () => {
    server.use(
      http.get(`${API_V1}/activities/calendar`, () =>
        problem(422, 'range_too_long', 'The range cannot be longer than 92 days'),
      ),
    );
    renderList();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'El rango no puede superar los 92 días',
    );
  });
});

describe('Hoy view switcher', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('offers Día, Mes and Listado without changing route', async () => {
    const user = userEvent.setup();
    renderRoutes([{ path: '/hoy', element: <TodayPage /> }], { route: '/hoy' });

    const switcher = await screen.findByRole('group', { name: 'Vista' });
    expect(
      within(switcher)
        .getAllByRole('radio')
        .map((r) => r.parentElement?.textContent),
    ).toEqual(['Día', 'Mes', 'Listado']);

    await user.click(within(switcher).getByRole('radio', { name: 'Listado' }));

    expect(await screen.findByLabelText('Desde')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/');
  });
});
