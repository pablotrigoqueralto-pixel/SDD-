import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { tambre } from '@/test/msw/accounts-fixtures';
import { adminUser, problem, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { AccountForm } from './components/AccountForm';
import { AccountCreateRoute } from './pages/AccountFormRoute';
import { AccountListPage } from './pages/AccountListPage';

describe('AccountForm', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', adminUser);
  });

  it('shows three fields above the fold, hints from the province and creates', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/accounts`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...tambre, id: 'created', version: 1 }, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<AccountForm onSaved={onSaved} />);

    expect(screen.getByLabelText('Nombre')).toBeInTheDocument();
    const more = screen.getByRole('button', { name: 'Más datos (opcional)' });
    expect(more).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByLabelText('CIF/NIF')).not.toBeVisible();

    await user.type(screen.getByLabelText('Nombre'), 'Clínica Nueva');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tipo' }), 'Hospital público');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provincia' }), 'Madrid');
    expect(await screen.findByRole('note')).toHaveTextContent('Territorio: Centro');
    expect(screen.getByRole('note')).toHaveTextContent('se asigna automáticamente');

    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({
      name: 'Clínica Nueva',
      account_type_id: '019000000-0000-7000-8000-0000000000t2',
      province_code: '28',
      division_ids: [],
      brand_ids: [],
    });
  });

  it('tells a rep the account will be theirs and validates required fields in Spanish', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', repUser);
    renderWithProviders(<AccountForm onSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Indica el nombre del centro')).toBeInTheDocument();
    expect(screen.getByText('Selecciona el tipo de centro')).toBeInTheDocument();
    expect(screen.getByText('Selecciona la provincia')).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provincia' }), 'Barcelona');
    expect(await screen.findByRole('note')).toHaveTextContent('Comercial: tú');
  });

  it('reports a duplicate CIF under the field with a link to the existing centre', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API_V1}/accounts`, () =>
        HttpResponse.json(
          {
            type: 'https://crm.quermed.com/problems/tax-id-already-exists',
            title: 'dup',
            status: 409,
            detail: 'dup',
            code: 'tax_id_already_exists',
            trace_id: 't',
            existing_account_id: tambre.id,
          },
          { status: 409, headers: { 'Content-Type': 'application/problem+json' } },
        ),
      ),
    );
    renderWithProviders(<AccountForm onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText('Nombre'), 'Dup');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tipo' }), 'Hospital público');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provincia' }), 'Madrid');
    await user.click(screen.getByRole('button', { name: 'Más datos (opcional)' }));
    await user.type(screen.getByLabelText('CIF/NIF'), 'B12345674');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Ya existe un centro con este CIF')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver centro existente' })).toHaveAttribute(
      'href',
      `/centros/${tambre.id}`,
    );
  });

  it('surfaces backend field errors under their field and opens the section', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API_V1}/accounts`, () =>
        problem(422, 'postal_code_invalid', 'bad', [
          { field: 'postal_code', message: 'bad', code: 'postal_code_invalid' },
        ]),
      ),
    );
    renderWithProviders(<AccountForm onSaved={vi.fn()} />);
    await user.type(screen.getByLabelText('Nombre'), 'X');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tipo' }), 'Hospital público');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provincia' }), 'Madrid');

    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('El código postal debe tener 5 dígitos')).toBeInTheDocument();
    expect(screen.getByLabelText('CIF/NIF')).toBeVisible();
  });

  it('edits sending only the changed fields with the version and opens the conflict dialog', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    server.use(
      http.patch(`${API_V1}/accounts/:id`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...tambre, ...body, version: 4 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<AccountForm account={tambre} onSaved={onSaved} />);

    expect(screen.getByRole('button', { name: 'Más datos (opcional)' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    await user.clear(screen.getByLabelText('Ciudad'));
    await user.type(screen.getByLabelText('Ciudad'), 'Alcobendas');
    await user.clear(screen.getByLabelText('Código Sage'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(ifMatch).toBe('"3"');
    expect(body).toEqual({ city: 'Alcobendas', customer_code: null });
  });

  it('navigates to the created centre from the create route', async () => {
    const user = userEvent.setup();
    renderRoutes(
      [
        {
          path: '/centros',
          element: <AccountListPage />,
          children: [{ path: 'nuevo', element: <AccountCreateRoute /> }],
        },
        { path: '/centros/:accountId', element: <h1>Detalle</h1> },
      ],
      { route: '/centros/nuevo' },
    );
    const dialog = await screen.findByRole('dialog');

    await user.type(screen.getByLabelText('Nombre'), 'Clínica Nueva');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tipo' }), 'Hospital público');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Provincia' }), 'Madrid');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByRole('heading', { name: 'Detalle' })).toBeInTheDocument();
    expect(dialog).not.toBeInTheDocument();
  });
});
