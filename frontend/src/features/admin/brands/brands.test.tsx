import { renderHook, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { referenceKeys } from '@/api/query-keys';
import { Providers, createQueryClient } from '@/app/providers';
import { useConflictStore } from '@/store/conflict.store';
import { VASCULAR_ID, problem } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { HADECO_ID, brands } from '@/test/msw/reference-fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes, renderWithProviders } from '@/test/render';

import { BrandForm } from './components/BrandForm';
import { BrandListPage } from './pages/BrandListPage';
import { useBrandList, useCreateBrand, useUpdateBrand } from './queries';

afterEach(() => {
  vi.restoreAllMocks();
  useConflictStore.getState().dismiss();
});

describe('brand queries', () => {
  it('lists with filters, creates, and updates with If-Match invalidating the reference bundle', async () => {
    const queryClient = createQueryClient();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    const wrapper = ({ children }: { children: ReactNode }) => (
      <Providers queryClient={queryClient}>{children}</Providers>
    );
    let search = '';
    let ifMatch: string | null = null;
    server.use(
      http.get(`${API_V1}/brands`, ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(brands);
      }),
      http.patch(`${API_V1}/brands/:id`, ({ request }) => {
        ifMatch = request.headers.get('if-match');
        return HttpResponse.json({ ...brands[1]!, name: 'Hadeco Europe', version: 4 });
      }),
    );

    const { result } = renderHook(
      () => ({
        list: useBrandList({ q: 'ha', is_own: 'true' }),
        create: useCreateBrand(),
        update: useUpdateBrand(),
      }),
      { wrapper },
    );
    await waitFor(() => {
      expect(result.current.list.isSuccess).toBe(true);
    });
    expect(search).toBe('?q=ha&is_own=true');

    const created = await result.current.create.mutateAsync({
      name: 'Cook',
      is_own: false,
      division_ids: [],
    });
    const updated = await result.current.update.mutateAsync({
      id: HADECO_ID,
      version: 3,
      payload: { name: 'Hadeco Europe' },
    });

    expect(created.id).toBe('new-brand-id');
    expect(updated.version).toBe(4);
    expect(ifMatch).toBe('"3"');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: referenceKeys.all });
  });
});

function renderList(route = '/admin/marcas') {
  return renderRoutes(
    [
      { path: '/admin', element: <h1>Hub</h1> },
      {
        path: '/admin/marcas',
        element: <BrandListPage />,
        children: [
          { path: 'nueva', element: <p>Nueva form</p> },
          { path: ':brandId', element: <p>Edit form</p> },
        ],
      },
    ],
    { route },
  );
}

describe('BrandListPage', () => {
  it('shows kind badges, divisions and the inactive badge', async () => {
    renderList();

    const list = await screen.findByRole('list');
    expect(within(list).getAllByText('Propia')).toHaveLength(2);
    expect(within(list).getByText('Competencia')).toBeInTheDocument();
    expect(await within(list).findByText('Vascular')).toBeInTheDocument();
    const cook = screen.getByText('Cook Medical').closest('li');
    expect(within(cook!).getByText('Inactiva')).toBeInTheDocument();
  });

  it('applies search and kind filter through the URL and navigates to forms', async () => {
    const user = userEvent.setup();
    const searches: string[] = [];
    server.use(
      http.get(`${API_V1}/brands`, ({ request }) => {
        searches.push(new URL(request.url).search);
        return HttpResponse.json(brands);
      }),
    );
    renderList();
    await screen.findByText('Fertipro');

    await user.selectOptions(screen.getByLabelText('Tipo'), 'false');
    await user.type(screen.getByLabelText('Buscar'), 'co');
    await waitFor(() => {
      expect(searches.at(-1)).toBe('?q=co&is_own=false');
    });

    await user.click(screen.getAllByRole('button', { name: 'Nueva marca' })[0]!);
    expect(await screen.findByText('Nueva form')).toBeInTheDocument();
  });
});

describe('BrandForm', () => {
  it('creates a competitor brand with divisions', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/brands`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...brands[2]!, id: 'created' }, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<BrandForm onSaved={onSaved} />);
    await screen.findByLabelText('Vascular');

    await user.type(screen.getByLabelText('Nombre'), 'Cook Medical');
    await user.selectOptions(screen.getByLabelText('Tipo'), 'competitor');
    await user.click(screen.getByLabelText('Vascular'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({ name: 'Cook Medical', is_own: false, division_ids: [VASCULAR_ID] });
  });

  it('shows the duplicate name error under the field', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API_V1}/brands`, () => problem(409, 'brand_name_already_exists', 'dup')),
    );
    renderWithProviders(<BrandForm onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText('Nombre'), 'Fertipro');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Ya existe una marca con este nombre')).toBeInTheDocument();
  });

  it('edits with the version and opens the conflict dialog on 409', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    server.use(
      http.patch(`${API_V1}/brands/:id`, ({ request }) => {
        ifMatch = request.headers.get('if-match');
        return problem(409, 'conflict', 'stale');
      }),
    );
    renderWithProviders(<BrandForm brand={brands[1]!} onSaved={vi.fn()} />);
    await screen.findByLabelText('Vascular');

    expect(screen.getByLabelText('Vascular')).toBeChecked();
    await user.click(screen.getByLabelText('Activa'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(useConflictStore.getState().open).toBe(true);
    });
    expect(ifMatch).toBe('"3"');
  });
});
