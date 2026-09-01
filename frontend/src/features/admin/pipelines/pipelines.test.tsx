import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { problem } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { EQUIPMENT_ID, pipelines } from '@/test/msw/reference-fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { PipelinesPage } from './pages/PipelinesPage';

function renderPage() {
  return renderRoutes(
    [
      { path: '/admin', element: <h1>Hub</h1> },
      { path: '/admin/pipelines', element: <PipelinesPage /> },
    ],
    { route: '/admin/pipelines' },
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('PipelinesPage', () => {
  it('renders both pipelines with ordered stages, badges and accessible buttons', async () => {
    renderPage();

    const equipment = await screen.findByRole('region', { name: 'Equipos' });
    const rows = within(equipment).getAllByRole('listitem');
    expect(rows).toHaveLength(5);
    expect(rows[0]).toHaveTextContent('Contacto');
    expect(rows[0]).toHaveTextContent('10 %');
    // Stage name and badge both read 'Ganada' / 'Perdida'.
    expect(within(rows[3]!).getAllByText('Ganada')).toHaveLength(2);
    expect(within(rows[4]!).getAllByText('Perdida')).toHaveLength(2);
    expect(within(rows[0]!).getByRole('button', { name: 'Subir Contacto' })).toBeDisabled();
    expect(within(rows[0]!).getByRole('button', { name: 'Bajar Contacto' })).toBeEnabled();
    expect(within(rows[4]!).getByRole('button', { name: 'Bajar Perdida' })).toBeDisabled();
    expect(within(rows[1]!).getByRole('button', { name: 'Editar Demo' })).toBeInTheDocument();
    expect(within(equipment).getByText(/Por defecto para/)).toHaveTextContent('Vascular');

    const consumables = screen.getByRole('region', { name: 'Consumibles' });
    expect(within(consumables).getAllByText('En riesgo')).toHaveLength(2);
  });

  it('moves a stage down calling the order endpoint with If-Match', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: { stage_ids: string[] } = { stage_ids: [] };
    server.use(
      http.put(`${API_V1}/pipelines/:id/stages/order`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as { stage_ids: string[] };
        const pipeline = pipelines[0]!;
        const byId = new Map(pipeline.stages.map((s) => [s.id, s]));
        return HttpResponse.json({
          ...pipeline,
          version: 3,
          stages: body.stage_ids.map((id, i) => ({ ...byId.get(id)!, sort_order: i + 1 })),
        });
      }),
    );
    renderPage();
    const equipment = await screen.findByRole('region', { name: 'Equipos' });

    await user.click(within(equipment).getByRole('button', { name: 'Bajar Contacto' }));

    await waitFor(() => {
      expect(body.stage_ids.slice(0, 2)).toEqual(['s-demo', 's-contact']);
    });
    expect(ifMatch).toBe('"2"');
    expect(body.stage_ids).toHaveLength(5);
  });

  it('edits a stage probability through the form with the stage version', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    server.use(
      http.patch(`${API_V1}/pipelines/:id/stages/:stageId`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(pipelines[0]);
      }),
    );
    renderPage();
    const equipment = await screen.findByRole('region', { name: 'Equipos' });

    await user.click(within(equipment).getByRole('button', { name: 'Editar Demo' }));
    const dialog = await screen.findByRole('dialog');
    const probability = within(dialog).getByLabelText('Probabilidad (%)');
    await user.clear(probability);
    await user.type(probability, '40');
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(body).toEqual({ name: 'Demo', probability: 40, is_active: true });
    });
    expect(ifMatch).toBe('"1"');
    expect(EQUIPMENT_ID).toBe(pipelines[0]!.id);
  });

  it('validates the probability range locally and surfaces backend guards inline', async () => {
    const user = userEvent.setup();
    server.use(
      http.patch(`${API_V1}/pipelines/:id/stages/:stageId`, () =>
        problem(400, 'last_active_stage', 'last'),
      ),
    );
    renderPage();
    const equipment = await screen.findByRole('region', { name: 'Equipos' });

    await user.click(within(equipment).getByRole('button', { name: 'Editar Demo' }));
    const dialog = await screen.findByRole('dialog');
    const probability = within(dialog).getByLabelText('Probabilidad (%)');
    await user.clear(probability);
    await user.type(probability, '120');
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    expect(await within(dialog).findByText('Introduce un valor entre 0 y 100')).toBeInTheDocument();

    await user.clear(probability);
    await user.type(probability, '35');
    await user.click(within(dialog).getByLabelText('Activa'));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));
    expect(
      await within(dialog).findByText(
        'El pipeline debe conservar al menos una etapa abierta activa',
      ),
    ).toBeInTheDocument();
  });

  it('never offers a move that would lift a terminal stage', async () => {
    renderPage();

    const equipment = await screen.findByRole('region', { name: 'Equipos' });
    const rows = within(equipment).getAllByRole('listitem');

    // Rows: Contacto, Demo, Presupuesto, Ganada, Perdida.
    expect(within(rows[1]!).getByRole('button', { name: 'Bajar Demo' })).toBeEnabled();
    // The last advancing stage cannot go below Ganada…
    expect(within(rows[2]!).getByRole('button', { name: 'Bajar Presupuesto' })).toBeDisabled();
    // …and the first terminal stage cannot climb above it.
    expect(within(rows[3]!).getByRole('button', { name: 'Subir Ganada' })).toBeDisabled();
    expect(within(rows[4]!).getByRole('button', { name: 'Bajar Perdida' })).toBeDisabled();
    // Reordering the terminal stages among themselves breaks nothing and stays allowed.
    expect(within(rows[4]!).getByRole('button', { name: 'Subir Perdida' })).toBeEnabled();
  });
});
