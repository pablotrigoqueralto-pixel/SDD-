import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { useConflictStore } from '@/store/conflict.store';
import { doppler, gel } from '@/test/msw/catalogue-fixtures';
import { adminUser, problem, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { ProductForm } from './components/ProductForm';
import { CatalogueListPage } from './pages/CatalogueListPage';
import { ProductFormRoute } from './pages/ProductFormRoute';

const backOfficeUser = { ...adminUser, id: 'bo', role: 'back_office' as const };
const managerUser = { ...adminUser, id: 'mgr', role: 'sales_manager' as const };

function renderCatalogue(route = '/catalogo') {
  return renderRoutes(
    [
      {
        path: '/catalogo',
        element: <CatalogueListPage />,
        children: [
          { path: 'nuevo', element: <ProductFormRoute /> },
          { path: ':productId', element: <ProductFormRoute /> },
        ],
      },
    ],
    { route },
  );
}

describe('CatalogueListPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', adminUser);
  });

  it('lists active products as cards with brand, family, code and price', async () => {
    renderCatalogue();

    const list = await screen.findByRole('list');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Doppler ES-100');
    expect(items[0]).toHaveTextContent('Hadeco');
    expect(items[0]).toHaveTextContent('Dopplers');
    expect(items[0]).toHaveTextContent('HAD-1000');
    expect(items[0]!.textContent.replace(/[\u00a0\u202f]/g, ' ')).toContain('12.500,00 €');
    expect(within(items[0]!).getByText('Equipo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Nuevo producto' })).toBeInTheDocument();
  });

  it('searches by code after the debounce and keeps the filter in the URL', async () => {
    const user = userEvent.setup();
    const queries: string[] = [];
    server.use(
      http.get(`${API_V1}/products`, ({ request }) => {
        const url = new URL(request.url);
        queries.push(url.search);
        const q = url.searchParams.get('q');
        return HttpResponse.json({
          items: q ? [doppler] : [doppler, gel],
          total: q ? 1 : 2,
          page: 1,
          page_size: 25,
        });
      }),
    );
    renderCatalogue();
    await screen.findByRole('list');

    await user.type(screen.getByRole('searchbox', { name: 'Buscar' }), 'HAD-10');

    await waitFor(() => {
      expect(queries.some((query) => query.includes('q=HAD-10'))).toBe(true);
    });
    await waitFor(() => {
      expect(screen.getAllByRole('listitem')).toHaveLength(1);
    });
    await user.click(screen.getByRole('button', { name: 'Vascular' }));
    await waitFor(() => {
      expect(queries.some((query) => query.includes('division_id='))).toBe(true);
    });
    expect(screen.getByRole('button', { name: 'Vascular' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('hides the create action from a sales rep and opens a read-only product', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', repUser);
    renderCatalogue();

    await screen.findByRole('list');
    expect(screen.queryByRole('button', { name: 'Nuevo producto' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Doppler ES-100/ }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('heading', { name: 'Producto' })).toBeInTheDocument();
    expect(within(dialog).getByLabelText('Nombre')).toBeDisabled();
    expect(within(dialog).queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText('Coste')).not.toBeInTheDocument();
  });
});

describe('ProductForm', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', backOfficeUser);
    useConflictStore.getState().dismiss();
  });

  it('creates a product with six fields and Spanish decimals', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/products`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...doppler, id: 'created' }, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<ProductForm onSaved={onSaved} />);

    expect(screen.getByLabelText('Unidad')).not.toBeVisible();
    expect(screen.queryByLabelText('Coste')).not.toBeInTheDocument();
    await user.type(screen.getByLabelText('Código Sage'), 'had-2000');
    await user.type(screen.getByLabelText('Nombre'), 'Doppler ES-200');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Marca' }), 'Hadeco');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Familia' }), 'Dopplers');
    await user.click(screen.getByRole('radio', { name: 'Equipo' }));
    await user.type(screen.getByLabelText('Precio de lista'), '1.250,50');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({
      sku: 'had-2000',
      name: 'Doppler ES-200',
      brand_id: doppler.brand.id,
      family_id: doppler.family.id,
      kind: 'equipment',
      list_price: '1250.50',
    });
  });

  it('validates required fields in Spanish', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProductForm onSaved={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Indica el código Sage')).toBeInTheDocument();
    expect(screen.getByText('Selecciona el tipo')).toBeInTheDocument();
    expect(screen.getByText('Indica el precio de lista')).toBeInTheDocument();
  });

  it('shows a duplicate code under the field with a link to the existing product', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API_V1}/products`, () =>
        HttpResponse.json(
          {
            type: 'https://crm.quermed.com/problems/product-sku-exists',
            title: 'dup',
            status: 409,
            detail: 'dup',
            code: 'product_sku_exists',
            existing_product_id: doppler.id,
          },
          { status: 409 },
        ),
      ),
    );
    renderRoutes(
      [
        { path: '/form', element: <ProductForm onSaved={vi.fn()} /> },
        { path: '/catalogo/:productId', element: <h1>Existente</h1> },
      ],
      { route: '/form' },
    );

    await user.type(screen.getByLabelText('Código Sage'), 'HAD-1000');
    await user.type(screen.getByLabelText('Nombre'), 'Dup');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Marca' }), 'Hadeco');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Familia' }), 'Dopplers');
    await user.click(screen.getByRole('radio', { name: 'Consumible' }));
    await user.type(screen.getByLabelText('Precio de lista'), '10');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(
      await screen.findByText('Ya existe un producto con este código Sage'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Ver el producto existente' }));
    expect(await screen.findByText('Existente')).toBeInTheDocument();
  });

  it('lets a manager see the cost but not edit', () => {
    sessionStore.getState().setSession('token', managerUser);
    renderWithProviders(<ProductForm product={doppler} onSaved={vi.fn()} />);

    expect(screen.getByLabelText('Coste')).toHaveValue('8000,00');
    expect(screen.getByLabelText('Coste')).toBeDisabled();
    expect(screen.getByRole('note')).toHaveTextContent('Solo administración puede editar');
    expect(screen.queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument();
  });

  it('opens the conflict dialog on 409', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', adminUser);
    server.use(http.patch(`${API_V1}/products/:id`, () => problem(409, 'conflict', 'stale')));
    renderWithProviders(<ProductForm product={doppler} onSaved={vi.fn()} />);

    const nameInput = screen.getByLabelText('Nombre');
    await user.clear(nameInput);
    await user.type(nameInput, 'Doppler ES-100 Plus');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(useConflictStore.getState().open).toBe(true);
    });
  });

  it('sends only changed fields with the version and toggles the state separately', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', adminUser);
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    let deactivated = false;
    server.use(
      http.patch(`${API_V1}/products/:id`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...doppler, ...body, version: 2 });
      }),
      http.post(`${API_V1}/products/:id/deactivate`, ({ request }) => {
        deactivated = request.headers.get('if-match') === '"2"';
        return HttpResponse.json({ ...doppler, is_active: false, version: 3 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<ProductForm product={doppler} onSaved={onSaved} />);

    const price = screen.getByLabelText('Precio de lista');
    await user.clear(price);
    await user.type(price, '13.000');
    const cost = screen.getByLabelText('Coste');
    await user.clear(cost);
    await user.click(screen.getByLabelText('Activo'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(ifMatch).toBe('"1"');
    expect(body).toEqual({ list_price: '13000.00', cost_price: null });
    expect(deactivated).toBe(true);
  });
});
