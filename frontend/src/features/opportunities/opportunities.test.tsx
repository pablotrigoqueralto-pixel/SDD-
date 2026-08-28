import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { tambre } from '@/test/msw/accounts-fixtures';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import {
  DEMO_STAGE,
  QUOTE_STAGE,
  board,
  doppler,
  tenderOpportunity,
} from '@/test/msw/opportunities-fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { OpportunityForm } from './components/OpportunityForm';
import { OpportunityPage } from './pages/OpportunityPage';
import { OpportunityDialogRoute } from './pages/OpportunityRoutes';
import { PipelinePage } from './pages/PipelinePage';

const backOfficeUser = { ...adminUser, id: 'bo', role: 'back_office' as const };

function renderPipeline(route = '/oportunidades') {
  return renderRoutes(
    [
      { path: '/oportunidades', element: <PipelinePage /> },
      { path: '/oportunidades/:opportunityId', element: <h1>Detalle</h1> },
    ],
    { route },
  );
}

function renderSheet(route = `/oportunidades/${doppler.id}`) {
  return renderRoutes(
    [
      {
        path: '/oportunidades/:opportunityId',
        element: <OpportunityPage />,
        children: [
          { path: 'ganar', element: <OpportunityDialogRoute kind="win" /> },
          { path: 'perder', element: <OpportunityDialogRoute kind="lose" /> },
          { path: 'editar', element: <OpportunityDialogRoute kind="edit" /> },
        ],
      },
    ],
    { route },
  );
}

describe('PipelinePage (mobile list)', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('lists open opportunities with badges and days in stage by default', async () => {
    const queries: string[] = [];
    server.use(
      http.get(`${API_V1}/opportunities`, ({ request }) => {
        queries.push(new URL(request.url).search);
        return HttpResponse.json({
          items: [
            {
              ...tenderOpportunity,
              id: tenderOpportunity.id,
            },
          ].map((o) => ({
            id: o.id,
            account_id: o.account_id,
            account_name: o.account_name,
            name: o.name,
            pipeline_id: o.pipeline_id,
            stage_id: o.stage_id,
            stage_name: o.stage_name,
            division_id: o.division_id,
            owner_id: o.owner_id,
            owner_name: o.owner_name,
            status: o.status,
            amount: o.amount,
            expected_close_date: o.expected_close_date,
            is_tender: o.is_tender,
            tender_deadline: o.tender_deadline,
            is_at_risk: o.is_at_risk,
            stage_entered_at: o.stage_entered_at,
            days_in_stage: o.days_in_stage,
            version: o.version,
            updated_at: o.updated_at,
          })),
          total: 1,
          page: 1,
          page_size: 25,
        });
      }),
    );
    renderPipeline();

    const list = await screen.findByRole('list');
    const item = within(list).getAllByRole('listitem')[0]!;
    expect(item).toHaveTextContent('H. La Paz · Vascular · agosto 2026');
    expect(item).toHaveTextContent('Licitación');
    expect(item).toHaveTextContent('12 días en etapa');
    expect(queries.every((query) => !query.includes('status='))).toBe(true);
  });

  it('switches to lost with the state chip', async () => {
    const user = userEvent.setup();
    const queries: string[] = [];
    server.use(
      http.get(`${API_V1}/opportunities`, ({ request }) => {
        queries.push(new URL(request.url).search);
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
    );
    renderPipeline();
    await screen.findByText('No hay oportunidades que coincidan');

    await user.click(screen.getByRole('button', { name: 'Perdidas' }));

    await waitFor(() => {
      expect(queries.some((query) => query.includes('status=lost'))).toBe(true);
    });
    expect(screen.getByRole('button', { name: 'Perdidas' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});

describe('OpportunityForm', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('creates with three fields and Spanish decimals', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/opportunities`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...doppler, id: 'created' }, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<OpportunityForm accountId={tambre.id} onSaved={onSaved} />);

    await screen.findByRole('option', { name: 'Vascular' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'División' }), 'Vascular');
    expect(await screen.findByRole('note')).toHaveTextContent('Pipeline: Equipos');
    await user.type(screen.getByLabelText('Importe estimado'), '30.000');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({
      account_id: tambre.id,
      division_id: doppler.division_id,
      estimated_amount: '30000.00',
    });
  });

  it('validates required fields in Spanish', async () => {
    const user = userEvent.setup();
    renderWithProviders(<OpportunityForm accountId={tambre.id} onSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Indica el importe estimado')).toBeInTheDocument();
    expect(screen.getAllByText('Selecciona la división').length).toBeGreaterThanOrEqual(2);
  });
});

describe('OpportunityPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('loses with Competidor requiring the brand inline', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/opportunities/:id/lose`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...doppler, status: 'lost', version: 3 });
      }),
    );
    renderSheet(`/oportunidades/${doppler.id}/perder`);

    const dialog = await screen.findByRole('dialog');
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Motivo' }),
      'Competidor',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Perder' }));
    expect(await within(dialog).findByText('Indica la marca competidora')).toBeInTheDocument();

    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Marca competidora' }),
      'Hadeco',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Perder' }));

    await waitFor(() => {
      expect(body.competitor_brand_id).toBeTruthy();
    });
  });

  it('adds a product line with If-Match and the default quantity handling', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/opportunities/:id/lines`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...doppler, amount: '25000.00', version: 3 }, { status: 201 });
      }),
    );
    renderSheet();

    expect(
      await screen.findByText('Sin productos: se usa el importe estimado'),
    ).toBeInTheDocument();
    await screen.findAllByRole('option', { name: /Doppler ES-100/ });
    await user.selectOptions(
      screen.getByRole('combobox', { name: /Producto/ }),
      screen.getAllByRole('option', { name: /Doppler ES-100/ })[0]!,
    );
    const quantity = screen.getByLabelText('Cantidad');
    await user.clear(quantity);
    await user.type(quantity, '2');
    await user.click(screen.getByRole('button', { name: 'Añadir producto' }));

    await waitFor(() => {
      expect(body.quantity).toBe('2.00');
    });
    expect(ifMatch).toBe('"2"');
    expect(body.unit_price).toBeUndefined();
  });

  it('is read-only for back office', async () => {
    sessionStore.getState().setSession('token', backOfficeUser);
    renderSheet();

    await screen.findByRole('heading', { name: doppler.name });
    expect(screen.queryByRole('button', { name: 'Ganar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Perder' })).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Etapa' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Añadir producto' })).not.toBeInTheDocument();
  });

  it('shows the stage history', async () => {
    renderSheet();

    expect(await screen.findByText('Contacto → Demo')).toBeInTheDocument();
    expect(screen.getByText('Creada en Contacto')).toBeInTheDocument();
  });
});

describe('Board (desktop)', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', adminUser);
    window.matchMedia = (query: string) => ({
      matches: true,
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      onchange: null,
      dispatchEvent: () => false,
    });
  });

  it('renders columns with counts, totals, the closed summary and close zones', async () => {
    renderPipeline();

    const demoColumn = await screen.findByRole('region', { name: DEMO_STAGE.name_es });
    expect(within(demoColumn).getByText(/1 · 30\.000,00/)).toBeInTheDocument();
    const quoteColumn = screen.getByRole('region', { name: QUOTE_STAGE.name_es });
    expect(within(quoteColumn).getByText(/1 · 60\.000,00/)).toBeInTheDocument();
    expect(screen.getByText(/Ganadas este mes: 1/)).toBeInTheDocument();
    expect(screen.getByLabelText('Ganada')).toBeInTheDocument();
    expect(screen.getByLabelText('Perdida')).toBeInTheDocument();
    expect(
      within(demoColumn).getAllByRole('button', {
        name: new RegExp(board.columns[1]!.items[0]!.name),
      }).length,
    ).toBeGreaterThan(0);
  });
});
