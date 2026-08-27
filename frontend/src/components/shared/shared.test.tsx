import type { QueryClient } from '@tanstack/react-query';
import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createQueryClient } from '@/app/providers';
import { problemFromBody } from '@/lib/problem';
import { useConflictStore } from '@/store/conflict.store';
import { renderWithProviders } from '@/test/render';

import { ConflictDialog } from './ConflictDialog';
import { DataList, type DataListColumn } from './DataList';
import { OfflineBanner } from './OfflineBanner';

function mockViewport(desktop: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    matches: desktop && query.includes('1024px'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

afterEach(() => {
  vi.restoreAllMocks();
  useConflictStore.getState().dismiss();
});

describe('OfflineBanner', () => {
  it('appears when going offline and hides on reconnection', () => {
    const onLine = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    renderWithProviders(<OfflineBanner />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();

    onLine.mockReturnValue(false);
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    expect(screen.getByRole('status')).toHaveTextContent(
      'Sin conexión. Los datos mostrados pueden no estar actualizados',
    );

    onLine.mockReturnValue(true);
    act(() => {
      window.dispatchEvent(new Event('online'));
    });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('ConflictDialog', () => {
  it('opens on a 409 mutation error and reloads the given queries', async () => {
    const user = userEvent.setup();
    const queryClient: QueryClient = createQueryClient();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    renderWithProviders(<ConflictDialog />, { queryClient });

    const mutation = queryClient.getMutationCache().build(queryClient, {
      mutationFn: () => Promise.reject(problemFromBody(409, { code: 'conflict' })),
      meta: { conflictKeys: [['users', 'detail', '1']] },
    });
    await mutation.execute(undefined).catch(() => undefined);

    const dialog = await screen.findByRole('dialog');
    expect(
      within(dialog).getByText('Otro usuario ha modificado este registro'),
    ).toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: 'Recargar' }));

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['users', 'detail', '1'] });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

interface Row {
  id: string;
  name: string;
  role: string;
}

const columns: DataListColumn<Row>[] = [
  { key: 'name', header: 'Nombre', cell: (row) => row.name },
  { key: 'role', header: 'Rol', cell: (row) => row.role },
];
const rows: Row[] = [
  { id: '1', name: 'Ana', role: 'Comercial' },
  { id: '2', name: 'Bea', role: 'Administración' },
];

describe('DataList', () => {
  it('renders cards below the desktop breakpoint', () => {
    mockViewport(false);
    renderWithProviders(
      <DataList
        items={rows}
        columns={columns}
        getKey={(r) => r.id}
        isLoading={false}
        emptyTitle="Vacío"
      />,
    );

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('Comercial')).toBeInTheDocument();
  });

  it('renders a table at the desktop breakpoint and selects rows', async () => {
    mockViewport(true);
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <DataList
        items={rows}
        columns={columns}
        getKey={(r) => r.id}
        onSelect={onSelect}
        isLoading={false}
        emptyTitle="Vacío"
      />,
    );

    const table = screen.getByRole('table');
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Nombre', 'Rol']);
    await user.click(within(table).getByText('Bea'));
    expect(onSelect).toHaveBeenCalledWith(rows[1]);
  });

  it('shows loading, empty and error states', () => {
    mockViewport(false);
    const { rerender } = renderWithProviders(
      <DataList
        items={undefined}
        columns={columns}
        getKey={(r) => r.id}
        isLoading
        emptyTitle="Vacío"
      />,
    );
    expect(screen.getByLabelText('Cargando…')).toBeInTheDocument();

    rerender(
      <DataList
        items={[]}
        columns={columns}
        getKey={(r) => r.id}
        isLoading={false}
        emptyTitle="Nada aquí"
      />,
    );
    expect(screen.getByText('Nada aquí')).toBeInTheDocument();

    const onRetry = vi.fn();
    rerender(
      <DataList
        items={undefined}
        columns={columns}
        getKey={(r) => r.id}
        isLoading={false}
        error={problemFromBody(500, { code: 'internal_error' })}
        onRetry={onRetry}
        emptyTitle="Vacío"
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('No se ha podido cargar');
    screen.getByRole('button', { name: 'Reintentar' }).click();
    expect(onRetry).toHaveBeenCalled();
  });
});
