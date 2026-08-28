import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { API_V1 } from '@/test/msw/handlers';
import { productFamilies, referenceBundle } from '@/test/msw/reference-fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { ProductFamilyFormRoute, ProductFamilyListPage } from './pages/ProductFamilyListPage';

function renderList(route = '/admin/familias') {
  return renderRoutes(
    [
      { path: '/admin', element: <h1>Hub</h1> },
      {
        path: '/admin/familias',
        element: <ProductFamilyListPage />,
        children: [
          { path: 'nueva', element: <ProductFamilyFormRoute /> },
          { path: ':familyId', element: <ProductFamilyFormRoute /> },
        ],
      },
    ],
    { route },
  );
}

describe('ProductFamilyListPage', () => {
  it('groups families by division and marks inactive ones', async () => {
    renderList();

    const headings = await screen.findAllByRole('heading', { level: 2 });
    expect(headings.map((heading) => heading.textContent)).toEqual(['Vascular', 'Neurología']);
    const lists = screen.getAllByRole('list');
    const vascular = within(lists[0]!).getAllByRole('listitem');
    expect(vascular).toHaveLength(2);
    expect(vascular[1]).toHaveTextContent('Ecógrafos vasculares');
    expect(within(vascular[1]!).getByText('Inactivo')).toBeInTheDocument();
  });

  it('creates a family in a division and refreshes the bundle', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    let bundleRequests = 0;
    server.use(
      http.post(`${API_V1}/product-families`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { ...productFamilies[0]!, id: 'created', name_es: body.name, sort_order: 30 },
          { status: 201 },
        );
      }),
      http.get(`${API_V1}/reference-data`, () => {
        bundleRequests += 1;
        return HttpResponse.json(referenceBundle);
      }),
    );
    renderList('/admin/familias/nueva');
    await screen.findAllByRole('heading', { level: 2 });
    const requestsBefore = bundleRequests;

    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText('Nombre'), 'Láser');
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'División' }),
      'Vascular',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(body).toEqual({ name: 'Láser', division_id: productFamilies[0]!.division_id });
    await waitFor(() => {
      expect(bundleRequests).toBeGreaterThan(requestsBefore);
    });
  });

  it('locks the division when editing', async () => {
    const user = userEvent.setup();
    renderList();

    await user.click(await screen.findByRole('button', { name: /Dopplers/ }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText('Nombre')).toHaveValue('Dopplers');
    expect(within(dialog).getByRole('combobox', { name: 'División' })).toBeDisabled();
    expect(within(dialog).getByLabelText('Orden')).toHaveValue('10');
  });
});
