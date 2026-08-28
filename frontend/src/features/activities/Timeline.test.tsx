import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { AccountPage } from '@/features/accounts';
import { sessionStore } from '@/features/auth';
import { tambre } from '@/test/msw/accounts-fixtures';
import { overdueVisit, timeline, visitDone } from '@/test/msw/activities-fixtures';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { ActivityDetailRoute } from './pages/ActivityRoutes';
import { TimelinePage } from './pages/TimelinePage';

function renderTree(route: string) {
  return renderRoutes(
    [
      {
        path: '/centros/:accountId',
        element: <AccountPage />,
        children: [{ path: 'actividades/:activityId', element: <ActivityDetailRoute /> }],
      },
      { path: '/centros/:accountId/actividades', element: <TimelinePage /> },
    ],
    { route },
  );
}

describe('timeline', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('shows the five most recent entries in the 360º page with "Ver todas"', async () => {
    const seen: string[] = [];
    const many = Array.from({ length: 7 }, (_, index) => ({
      ...timeline[0]!,
      id: `entry-${index}`,
      activity: { ...visitDone, id: `entry-${index}`, subject: `Visita ${index}` },
    }));
    server.use(
      http.get(`${API_V1}/accounts/:id/timeline`, ({ request }) => {
        const url = new URL(request.url);
        seen.push(url.searchParams.get('page_size') ?? '');
        const size = Number(url.searchParams.get('page_size') ?? '25');
        return HttpResponse.json({
          items: many.slice(0, size),
          total: 7,
          page: 1,
          page_size: size,
        });
      }),
    );
    renderTree(`/centros/${tambre.id}`);

    const sections = await screen.findAllByRole('button', { name: 'Actividades' });
    expect(sections.length).toBeGreaterThan(0);
    expect(await screen.findAllByText('Visita 4')).not.toHaveLength(0);
    expect(screen.queryByText('Visita 5')).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Ver todas (7)' })[0]).toHaveAttribute(
      'href',
      `/centros/${tambre.id}/actividades`,
    );
    expect(seen).toContain('5');
    expect(screen.getAllByRole('button', { name: 'Nueva actividad' }).length).toBeGreaterThan(0);
  });

  it('renders the full page with filters and actions on planned entries', async () => {
    const user = userEvent.setup();
    const seen: string[] = [];
    server.use(
      http.get(`${API_V1}/accounts/:id/timeline`, ({ request }) => {
        const url = new URL(request.url);
        seen.push(url.searchParams.get('status') ?? '');
        const status = url.searchParams.get('status');
        const items = status ? timeline.filter((e) => e.activity!.status === status) : timeline;
        return HttpResponse.json({ items, total: items.length, page: 1, page_size: 25 });
      }),
    );
    renderTree(`/centros/${tambre.id}/actividades`);

    expect(
      await screen.findByRole('heading', { name: 'Actividades · Clínica Tambre' }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole('article')).toHaveLength(3);
    const planned = screen.getAllByRole('article')[0]!;
    expect(within(planned).getByRole('button', { name: 'Cancelar actividad' })).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Estado' }), 'Hecha');
    expect(await screen.findByText('Demo Hadeco')).toBeInTheDocument();
    expect(seen.at(-1)).toBe('done');
  });

  it('opens the edit sheet for an editable activity and read-only when locked', async () => {
    const stale = {
      ...visitDone,
      id: 'old-visit',
      done_at: new Date(Date.now() - 10 * 86_400_000).toISOString(),
    };
    server.use(
      http.get(`${API_V1}/activities/:id`, ({ params }) =>
        HttpResponse.json(params.id === 'old-visit' ? stale : overdueVisit),
      ),
    );
    const editable = renderTree(`/centros/${tambre.id}/actividades/${overdueVisit.id}`);
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByRole('radio', { name: 'Visita' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Hecha' })).toBeInTheDocument();
    editable.unmount();

    renderTree(`/centros/${tambre.id}/actividades/old-visit`);
    const locked = await screen.findByRole('dialog');
    expect(
      await within(locked).findByText('Solo dirección comercial puede editar esta actividad'),
    ).toBeInTheDocument();
    expect(within(locked).queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument();

    sessionStore.getState().setSession('token', { ...adminUser, role: 'sales_manager' });
  });
});
