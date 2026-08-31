import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { MorePage } from '@/app/pages/MorePage';
import { sessionStore } from '@/features/auth';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { dashboardPayload } from '@/test/msw/handlers/dashboard';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { DashboardTeaser } from './components/DashboardTeaser';
import { InformesPage } from './pages/InformesPage';

const managerUser = { ...adminUser, id: 'mgr', role: 'sales_manager' as const };

function renderInformes() {
  return renderRoutes(
    [
      { path: '/informes', element: <InformesPage /> },
      { path: '/centros/:accountId', element: <h1>Centro detalle</h1> },
    ],
    { route: '/informes' },
  );
}

describe('InformesPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', managerUser);
  });

  it('renders the KPI cards with previous-period comparison and counts', async () => {
    renderInformes();

    expect((await screen.findAllByText(/30\.000,00\s*€/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Ganado').length).toBeGreaterThan(0);
    expect(screen.getByText(/Anterior: 20\.000,00\s*€/)).toBeInTheDocument();
    expect(screen.getByText(/3 de 5/)).toBeInTheDocument();
    expect(screen.getByText('60 %')).toBeInTheDocument();
    expect(screen.getAllByText(/4\.?914,00\s*€/).length).toBeGreaterThan(0);
    expect(screen.getByText('Importe × probabilidad de etapa')).toBeInTheDocument();
    expect(screen.getAllByText(/52\.000,00\s*€/).length).toBeGreaterThan(0);
  });

  it('shows an em dash when nothing closed instead of a fake 0%', async () => {
    server.use(
      http.get(`${API_V1}/dashboard`, () => {
        const payload = dashboardPayload();
        payload.summary.conversion = { rate: null, won: 0, closed: 0, previous_rate: null };
        return HttpResponse.json(payload);
      }),
    );
    renderInformes();

    const conversionCard = (await screen.findByText('Conversión')).closest('div');
    expect(conversionCard).not.toBeNull();
    expect(within(conversionCard as HTMLElement).getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('0 %')).not.toBeInTheDocument();
  });

  it('renders stage rows in order with figures as real text', async () => {
    renderInformes();

    const section = await screen.findByRole('region', { name: 'Pipeline por etapa' });
    const rows = within(section).getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('Contacto');
    expect(rows[0]).toHaveTextContent(/30\.000,00\s*€/);
    expect(rows[0]).toHaveTextContent('4 oportunidades');
    expect(rows[1]).toHaveTextContent('Demo');
    expect(rows[1]).toHaveTextContent(/22\.000,00\s*€/);
  });

  it('switching the period requests the quarter panel', async () => {
    const user = userEvent.setup();
    const periods: string[] = [];
    server.use(
      http.get(`${API_V1}/dashboard`, ({ request }) => {
        const period = new URL(request.url).searchParams.get('period') ?? 'month';
        periods.push(period);
        return HttpResponse.json(dashboardPayload(period as 'month' | 'quarter' | 'year'));
      }),
    );
    renderInformes();
    await screen.findByText('Ganado');

    await user.click(screen.getByRole('radio', { name: 'Trimestre' }));

    await waitFor(() => {
      expect(periods).toContain('quarter');
    });
  });

  it('hides Por comercial for a sales rep', async () => {
    sessionStore.getState().setSession('token', repUser);
    server.use(
      http.get(`${API_V1}/dashboard`, () =>
        HttpResponse.json({ ...dashboardPayload(), by_rep: null }),
      ),
    );
    renderInformes();

    await screen.findByText('Ganado');
    expect(screen.queryByText('Por comercial')).not.toBeInTheDocument();
    expect(screen.getByText('Por división')).toBeInTheDocument();
  });

  it('shows the error state with retry and recovers', async () => {
    const user = userEvent.setup();
    let failures = 0;
    server.use(
      http.get(`${API_V1}/dashboard`, () => {
        if (failures === 0) {
          failures += 1;
          return HttpResponse.json({ title: 'boom', status: 500 }, { status: 500 });
        }
        return HttpResponse.json(dashboardPayload());
      }),
    );
    renderInformes();

    const alert = await screen.findByRole('alert');
    await user.click(within(alert).getByRole('button'));

    expect(await screen.findByText('Ganado')).toBeInTheDocument();
  });

  it('shows empty states for sections without rows', async () => {
    server.use(
      http.get(`${API_V1}/dashboard`, () =>
        HttpResponse.json({
          ...dashboardPayload(),
          pipeline_by_stage: [],
          by_division: [],
          by_rep: [],
          activity: [],
          neglected_accounts: { total: 0, items: [] },
        }),
      ),
    );
    renderInformes();

    await screen.findByText('Ganado');
    expect(screen.getAllByText('Sin datos en este período').length).toBeGreaterThanOrEqual(2);
  });

  it('renders activity per rep with type counts and neglected accounts that navigate', async () => {
    const user = userEvent.setup();
    renderInformes();

    const activity = await screen.findByRole('region', { name: 'Actividad' });
    const row = within(activity).getByText('Laura Vendedora').closest('li');
    expect(row).toHaveTextContent('5 actividades');
    expect(row).toHaveTextContent('Visita 3');
    expect(row).toHaveTextContent('Llamada 2');

    const neglected = screen.getByRole('region', { name: 'Centros descuidados' });
    expect(within(neglected).getByText('2')).toBeInTheDocument();
    expect(within(neglected).getByText('Nunca')).toBeInTheDocument();
    expect(within(neglected).getByText(/hace 75 días/)).toBeInTheDocument();

    await user.click(within(neglected).getByRole('button', { name: /Clínica Tambre/ }));
    expect(await screen.findByText('Centro detalle')).toBeInTheDocument();
  });
});

describe('Informes card in Más', () => {
  it('is the first card for non-admin roles', async () => {
    sessionStore.getState().setSession('token', repUser);
    renderWithProviders(<MorePage />);

    const links = await screen.findAllByRole('link');
    expect(links[0]).toHaveTextContent('Informes');
  });

  it('follows Administración for admins', async () => {
    sessionStore.getState().setSession('token', adminUser);
    renderWithProviders(<MorePage />);

    const links = await screen.findAllByRole('link');
    expect(links[0]).toHaveTextContent('Administración');
    expect(links[1]).toHaveTextContent('Informes');
  });
});

describe('DashboardTeaser', () => {
  it('shows the month key figures for a manager and links to Informes', async () => {
    sessionStore.getState().setSession('token', managerUser);
    renderWithProviders(<DashboardTeaser />);

    const teaser = await screen.findByRole('link', { name: 'Cifras del mes' });
    expect(teaser).toHaveAttribute('href', '/informes');
    expect(teaser).toHaveTextContent(/30\.000,00\s*€/);
    expect(teaser).toHaveTextContent(/4\.?914,00\s*€/);
    expect(teaser).toHaveTextContent(/52\.000,00\s*€/);
    expect(teaser).toHaveTextContent('Ver informes');
  });

  it('renders nothing for a sales rep', () => {
    sessionStore.getState().setSession('token', repUser);
    const { container } = renderWithProviders(<DashboardTeaser />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for back office', () => {
    sessionStore.getState().setSession('token', { ...adminUser, role: 'back_office' });
    const { container } = renderWithProviders(<DashboardTeaser />);

    expect(container).toBeEmptyDOMElement();
  });

  it('disappears silently when the dashboard request fails', async () => {
    sessionStore.getState().setSession('token', managerUser);
    server.use(
      http.get(`${API_V1}/dashboard`, () =>
        HttpResponse.json({ title: 'boom', status: 500 }, { status: 500 }),
      ),
    );
    const { container } = renderWithProviders(<DashboardTeaser />);

    await waitFor(() => {
      expect(container).toBeEmptyDOMElement();
    });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
