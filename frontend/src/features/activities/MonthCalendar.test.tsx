import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/features/auth';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { CAL_REP_LAURA, CAL_REP_PEDRO, calendarPayload } from '@/test/msw/handlers/activities';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { TodayPage } from './pages/TodayPage';

const NOW = new Date();
const YEAR = NOW.getFullYear();
const MONTH = NOW.getMonth() + 1;

function renderHoy() {
  return renderRoutes(
    [
      { path: '/hoy', element: <TodayPage /> },
      { path: '/centros/:accountId/actividades/:activityId', element: <h1>Ficha actividad</h1> },
      { path: '/centros/:accountId', element: <h1>Detalle centro</h1> },
    ],
    { route: '/hoy' },
  );
}

function trackCalendarRequests(): { year: string; month: string; owner: string | null }[] {
  const seen: { year: string; month: string; owner: string | null }[] = [];
  server.use(
    http.get(`${API_V1}/activities/calendar`, ({ request }) => {
      const url = new URL(request.url);
      const year = url.searchParams.get('year') ?? '';
      const month = url.searchParams.get('month') ?? '';
      seen.push({ year, month, owner: url.searchParams.get('owner_id') });
      return HttpResponse.json(calendarPayload(Number(year), Number(month)));
    }),
  );
  return seen;
}

async function switchToMonth(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('radio', { name: 'Mes' }));
}

describe('Día ↔ Mes switcher', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('defaults to Día with the day plan untouched and no calendar request', async () => {
    const seen = trackCalendarRequests();
    renderHoy();

    expect(await screen.findByRole('region', { name: 'Atrasadas (1)' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Día' })).toBeChecked();
    expect(seen).toHaveLength(0);
  });

  it('switching to Mes requests exactly the current month once', async () => {
    const user = userEvent.setup();
    const seen = trackCalendarRequests();
    renderHoy();
    await screen.findByRole('region', { name: 'Atrasadas (1)' });

    await switchToMonth(user);

    await waitFor(() => {
      expect(seen).toHaveLength(1);
    });
    expect(seen[0]).toEqual({ year: String(YEAR), month: String(MONTH), owner: null });
    expect(screen.queryByRole('region', { name: 'Atrasadas (1)' })).not.toBeInTheDocument();
  });
});

describe('Month grid', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('renders Monday-first headers, day counts and dot overflow', async () => {
    const user = userEvent.setup();
    renderHoy();
    await switchToMonth(user);

    const grid = await screen.findByRole('grid');
    const headers = within(grid).getAllByRole('columnheader');
    expect(headers[0]).toHaveTextContent(/lun/i);
    expect(headers[6]).toHaveTextContent(/dom/i);

    expect(within(grid).getByRole('button', { name: /^10 de .*1 actividad$/ })).toBeInTheDocument();
    expect(
      within(grid).getByRole('button', { name: /^14 de .*2 actividades$/ }),
    ).toBeInTheDocument();
  });

  it('navigates months with one request each and returns with hoy', async () => {
    const user = userEvent.setup();
    const seen = trackCalendarRequests();
    renderHoy();
    await switchToMonth(user);
    await screen.findByRole('grid');

    await user.click(screen.getByRole('button', { name: 'Mes anterior' }));
    const previous =
      MONTH === 1
        ? { year: String(YEAR - 1), month: '12' }
        : { year: String(YEAR), month: String(MONTH - 1) };
    await waitFor(() => {
      expect(seen).toHaveLength(2);
    });
    expect(seen[1]).toEqual({ ...previous, owner: null });

    await user.click(screen.getByRole('button', { name: 'hoy' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^14 de /i })).toBeInTheDocument();
    });
  });
});

describe('Day expansion', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('lists the tapped day with done stated as text and navigates to the activity', async () => {
    const user = userEvent.setup();
    renderHoy();
    await switchToMonth(user);
    const grid = await screen.findByRole('grid');

    await user.click(within(grid).getByRole('button', { name: /^14 de / }));

    const dayList = await screen.findByRole('region', { name: /14 de/ });
    expect(within(dayList).getByText('09:30')).toBeInTheDocument();
    expect(within(dayList).getByText('Hecha')).toBeInTheDocument();
    expect(within(dayList).getByText('16:00')).toBeInTheDocument();

    await user.click(within(dayList).getByRole('button', { name: /Llamada/ }));
    expect(await screen.findByText('Ficha actividad')).toBeInTheDocument();
  });

  it('shows the empty state for a day without activities', async () => {
    const user = userEvent.setup();
    renderHoy();
    await switchToMonth(user);
    const grid = await screen.findByRole('grid');

    await user.click(within(grid).getByRole('button', { name: /^3 de / }));

    expect(await screen.findByText('Sin actividades este día')).toBeInTheDocument();
  });
});

describe('Team view', () => {
  it('offers the rep filter defaulting to Todos with a legend, and filters on selection', async () => {
    sessionStore.getState().setSession('token', adminUser);
    const user = userEvent.setup();
    const seen = trackCalendarRequests();
    server.use(
      http.get(`${API_V1}/users`, () =>
        HttpResponse.json({
          items: [
            { ...repUser, id: CAL_REP_LAURA, full_name: 'Laura Vendedora' },
            { ...repUser, id: CAL_REP_PEDRO, full_name: 'Pedro Vendedor' },
          ],
          total: 2,
          page: 1,
          page_size: 200,
        }),
      ),
    );
    renderHoy();
    await switchToMonth(user);
    await screen.findByRole('grid');

    const selector = screen.getByRole('combobox', { name: 'Comercial' });
    expect(selector).toHaveValue('');
    const legend = screen.getByRole('region', { name: 'Comerciales' });
    expect(within(legend).getByText('Laura Vendedora')).toBeInTheDocument();
    expect(within(legend).getByText('Pedro Vendedor')).toBeInTheDocument();

    await user.selectOptions(selector, CAL_REP_LAURA);
    await waitFor(() => {
      expect(seen.some((entry) => entry.owner === CAL_REP_LAURA)).toBe(true);
    });
  });

  it('renders no rep selector for a sales rep', async () => {
    sessionStore.getState().setSession('token', repUser);
    const user = userEvent.setup();
    renderHoy();
    await switchToMonth(user);
    await screen.findByRole('grid');

    expect(screen.queryByRole('combobox', { name: 'Comercial' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Comerciales' })).not.toBeInTheDocument();
  });
});
