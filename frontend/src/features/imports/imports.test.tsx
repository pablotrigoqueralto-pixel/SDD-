import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { RoleGate } from '@/app/guards';
import { sessionStore } from '@/features/auth';
import { adminUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { errorReportCsv } from './api';
import { ImportCataloguePage } from './pages/ImportPages';

const backOfficeUser = { ...adminUser, id: 'bo', role: 'back_office' as const };

function renderImport() {
  return renderRoutes([{ path: '/importar/catalogo', element: <ImportCataloguePage /> }], {
    route: '/importar/catalogo',
  });
}

function pickFile() {
  const input = document.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) throw new Error('file input not found');
  return { input, file: new File(['sku;name\nIMP-1;X\n'], 'productos.csv', { type: 'text/csv' }) };
}

describe('ImportFlow', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', backOfficeUser);
  });

  it('previews on file pick without confirming and shows outcomes with errors first', async () => {
    const user = userEvent.setup();
    const dryRuns: string[] = [];
    server.use(
      http.post(`${API_V1}/products/import`, ({ request }) => {
        dryRuns.push(new URL(request.url).searchParams.get('dry_run') ?? 'default');
        return HttpResponse.json({
          dry_run: true,
          created: 1,
          updated: 0,
          unchanged: 0,
          errors: 1,
          rows: [
            { row: 2, outcome: 'created', label: 'IMP-1', message: null },
            { row: 3, outcome: 'error', label: 'IMP-2', message: 'Unknown brand' },
          ],
        });
      }),
    );
    renderImport();

    const { input, file } = pickFile();
    await user.upload(input, file);

    expect(await screen.findByText('Vista previa')).toBeInTheDocument();
    expect(dryRuns).toEqual(['true']); // the client always previews first
    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('IMP-2'); // error rows come first
    expect(rows[1]).toHaveTextContent('Unknown brand');
    expect(screen.getByRole('button', { name: 'Importar 1 filas' })).toBeInTheDocument();
  });

  it('confirming posts dry_run=false and shows the applied totals', async () => {
    const user = userEvent.setup();
    const dryRuns: string[] = [];
    server.use(
      http.post(`${API_V1}/products/import`, ({ request }) => {
        const dryRun = new URL(request.url).searchParams.get('dry_run') !== 'false';
        dryRuns.push(String(dryRun));
        return HttpResponse.json({
          dry_run: dryRun,
          created: 2,
          updated: 0,
          unchanged: 0,
          errors: 0,
          rows: [
            { row: 2, outcome: 'created', label: 'IMP-1', message: null },
            { row: 3, outcome: 'created', label: 'IMP-2', message: null },
          ],
        });
      }),
    );
    renderImport();

    const { input, file } = pickFile();
    await user.upload(input, file);
    await user.click(await screen.findByRole('button', { name: 'Importar 2 filas' }));

    expect(await screen.findByText('Importación completada')).toBeInTheDocument();
    expect(screen.getByText('2 creados')).toBeInTheDocument();
    expect(dryRuns).toEqual(['true', 'false']);
  });

  it('builds the error CSV from the failing rows', () => {
    const csv = errorReportCsv({
      dry_run: false,
      created: 1,
      updated: 0,
      unchanged: 0,
      errors: 1,
      rows: [
        { row: 2, outcome: 'created', label: 'OK-1', message: null },
        { row: 5, outcome: 'error', label: 'BAD;X', message: 'Unknown brand;\nsecond line' },
      ],
    });

    expect(csv.split('\n')).toEqual(['fila;registro;error', '5;BAD,X;Unknown brand, second line']);
  });

  it('shows the file-level error on an invalid upload', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API_V1}/products/import`, () =>
        HttpResponse.json(
          {
            type: 'about:blank',
            title: 'Validation failed',
            status: 422,
            detail: 'Missing required columns: sku',
            code: 'validation_error',
          },
          { status: 422 },
        ),
      ),
    );
    renderImport();

    const { input, file } = pickFile();
    await user.upload(input, file);

    expect(await screen.findByRole('alert')).toHaveTextContent(/./);
    expect(screen.queryByText('Vista previa')).not.toBeInTheDocument();
  });
});

describe('role gating', () => {
  it('renders Sin permiso for a sales rep on the import route', async () => {
    sessionStore.getState().setSession('token', { ...adminUser, id: 'rep2', role: 'sales_rep' });
    renderRoutes(
      [
        {
          path: '/importar/catalogo',
          element: (
            <RoleGate roles={['admin', 'back_office']}>
              <ImportCataloguePage />
            </RoleGate>
          ),
        },
      ],
      { route: '/importar/catalogo' },
    );

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
    expect(screen.queryByText('Importar catálogo')).not.toBeInTheDocument();
  });
});
