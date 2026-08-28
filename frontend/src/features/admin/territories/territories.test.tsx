import { renderHook, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { Providers, createQueryClient } from '@/app/providers';
import { CENTRO_ID, page, problem, territories } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { TerritoryForm } from './components/TerritoryForm';
import { TerritoryListPage } from './pages/TerritoryListPage';
import { useTerritories } from './queries';

function wrapper({ children }: { children: ReactNode }) {
  return <Providers queryClient={createQueryClient()}>{children}</Providers>;
}

describe('territory queries', () => {
  it('loads territories', async () => {
    const { result } = renderHook(() => useTerritories(), { wrapper });

    await waitFor(() => {
      expect(result.current.data?.items[0]?.name).toBe('Centro');
    });
  });
});

describe('TerritoryListPage', () => {
  it('lists territories with province names and user counts', async () => {
    renderRoutes(
      [
        { path: '/admin', element: <h1>Hub</h1> },
        {
          path: '/admin/territorios',
          element: <TerritoryListPage />,
          children: [{ path: ':territoryId', element: <p>Edit form</p> }],
        },
      ],
      { route: '/admin/territorios' },
    );

    expect(await screen.findByText('Centro')).toBeInTheDocument();
    expect(screen.getByText('Madrid, Toledo')).toBeInTheDocument();
    expect(screen.getByText('1 usuario')).toBeInTheDocument();
  });
});

describe('TerritoryForm', () => {
  it('creates a territory from the province picker grouped by community', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/territories`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...territories[0]!, id: 'new', ...body }, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<TerritoryForm onSaved={onSaved} />);
    await screen.findByRole('group', { name: 'Andalucía' });

    await user.type(screen.getByLabelText('Nombre'), 'Sur');
    const andalucia = screen.getByRole('group', { name: 'Andalucía' });
    await user.click(within(andalucia).getByLabelText('Sevilla'));
    await user.click(within(andalucia).getByLabelText('Cádiz'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({ name: 'Sur', provinces: ['41', '11'] });
  });

  it('disables provinces owned by another territory and names the owner', async () => {
    renderWithProviders(<TerritoryForm onSaved={vi.fn()} />);

    expect((await screen.findAllByText('Provincia ya asignada a Centro')).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByLabelText(/Madrid/)).toBeDisabled();
    expect(screen.getByLabelText(/Sevilla/)).toBeEnabled();
  });

  it('requires at least one province', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TerritoryForm onSaved={vi.fn()} />);
    await screen.findByRole('group', { name: 'Andalucía' });

    await user.type(screen.getByLabelText('Nombre'), 'Sur');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Selecciona al menos una provincia')).toBeInTheDocument();
  });

  it('highlights the conflicting province returned by the backend', async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API_V1}/territories`, () => HttpResponse.json(page([]))),
      http.post(`${API_V1}/territories`, () =>
        problem(
          409,
          'province_already_assigned',
          "Province 41 is already assigned to territory 'Sur'",
        ),
      ),
    );
    renderWithProviders(<TerritoryForm onSaved={vi.fn()} />);
    await screen.findByRole('group', { name: 'Andalucía' });

    await user.type(screen.getByLabelText('Nombre'), 'Sur 2');
    await user.click(screen.getByLabelText('Sevilla'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Provincia ya asignada a otro territorio')).toBeInTheDocument();
    expect(screen.getByLabelText(/Sevilla/).closest('label')).toHaveTextContent(
      'Provincia ya asignada a Sur',
    );
  });

  it('edits with the version and surfaces territory_in_use on deactivation', async () => {
    const user = userEvent.setup();
    server.use(
      http.patch(`${API_V1}/territories/:id`, () =>
        problem(400, 'territory_in_use', 'The territory still has 1 active user(s) assigned'),
      ),
    );
    renderWithProviders(<TerritoryForm territory={territories[0]!} onSaved={vi.fn()} />);
    await screen.findByRole('group', { name: 'Andalucía' });

    await user.click(screen.getByLabelText('Activo'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(
      await screen.findByText('No se puede desactivar: tiene usuarios activos asignados'),
    ).toBeInTheDocument();
    expect(CENTRO_ID).toBe(territories[0]!.id);
  });
});
