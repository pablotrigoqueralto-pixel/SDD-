import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { sessionStore } from '@/features/auth';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { QUOTE_SENT_ID, draftQuote, expiredQuote, sentQuote } from '@/test/msw/quotes-fixtures';
import { server } from '@/test/msw/server';
import { renderRoutes } from '@/test/render';

import { QuoteSettingsPage } from './pages/QuoteSettingsPage';
import { QuotesListPage } from './pages/QuotesListPage';
import { QuoteRoutes } from './routes';

const backOfficeUser = { ...adminUser, id: 'bo', role: 'back_office' as const };
const managerUser = { ...adminUser, id: 'mgr', role: 'sales_manager' as const };

function renderList() {
  return renderRoutes(
    [
      { path: '/presupuestos', element: <QuotesListPage /> },
      { path: '/presupuestos/:quoteId', element: <h1>Detalle</h1> },
    ],
    { route: '/presupuestos' },
  );
}

function renderSheet(quoteId: string, subPath = '') {
  return renderRoutes([{ path: '/presupuestos/*', element: <QuoteRoutes /> }], {
    route: `/presupuestos/${quoteId}${subPath}`,
  });
}

describe('QuotesListPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('shows current versions with the Caducado visual on expired sent quotes', async () => {
    renderList();

    const rows = await screen.findAllByRole('listitem');
    const expired = rows.find((row) => row.textContent.includes(expiredQuote.display_number));
    expect(expired).toBeDefined();
    expect(expired).toHaveTextContent('Caducado');
    const sent = rows.find((row) => row.textContent.includes(sentQuote.display_number));
    expect(sent).toHaveTextContent('Enviado');
  });

  it('sends the expiring filter to the API', async () => {
    const user = userEvent.setup();
    const queries: string[] = [];
    server.use(
      http.get(`${API_V1}/quotes`, ({ request }) => {
        queries.push(new URL(request.url).search);
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 });
      }),
    );
    renderList();
    await screen.findByText('No hay presupuestos que coincidan');

    await user.click(screen.getByRole('checkbox', { name: 'Por caducar' }));
    await waitFor(() => {
      expect(queries.some((query) => query.includes('expiring=true'))).toBe(true);
    });
  });
});

describe('QuoteSheetPage actions per role and status', () => {
  it('owner rep sees draft actions and no cost column', async () => {
    sessionStore.getState().setSession('token', repUser);
    renderSheet(draftQuote.id);

    await screen.findByRole('heading', { name: draftQuote.display_number });
    expect(screen.getByRole('button', { name: 'Editar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Eliminar' })).toBeInTheDocument();
    expect(screen.queryByText('Coste')).not.toBeInTheDocument();
    expect(screen.queryByText('Margen')).not.toBeInTheDocument();
  });

  it('owner rep sees accept, reject and revise on a sent quote', async () => {
    sessionStore.getState().setSession('token', repUser);
    renderSheet(sentQuote.id);

    await screen.findByRole('heading', { name: sentQuote.display_number });
    expect(screen.getByRole('button', { name: 'Aceptar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rechazar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Nueva versión' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument();
  });

  it('back office edits drafts but never runs the lifecycle', async () => {
    sessionStore.getState().setSession('token', backOfficeUser);
    renderSheet(draftQuote.id);

    await screen.findByRole('heading', { name: draftQuote.display_number });
    expect(screen.getByRole('button', { name: 'Editar' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Enviar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aceptar' })).not.toBeInTheDocument();
  });

  it('managers see cost and margin', async () => {
    sessionStore.getState().setSession('token', managerUser);
    renderSheet(draftQuote.id);

    await screen.findByRole('heading', { name: draftQuote.display_number });
    expect(screen.getByText('Coste')).toBeInTheDocument();
    expect(screen.getByText('Margen')).toBeInTheDocument();
  });

  it('surfaces a failed email with the retry action', async () => {
    sessionStore.getState().setSession('token', repUser);
    renderSheet(expiredQuote.id);

    await screen.findByRole('heading', { name: expiredQuote.display_number });
    expect(screen.getByText(/El email falló/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar envío' })).toBeInTheDocument();
  });
});

describe('QuoteForm live totals', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('recomputes the per-line base and totals as the user types', async () => {
    const user = userEvent.setup();
    renderSheet(draftQuote.id, '/editar');

    const discount = await screen.findByLabelText('Dto. %');
    await user.clear(discount);
    await user.type(discount, '10');
    // 2 x 13.000 - 10 % = 23.400 base; IVA 21 % = 4.914; total 28.314
    expect((await screen.findAllByText(/23\.400,00/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4\.?914,00/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/28\.314,00/).length).toBeGreaterThan(0);
  });
});

describe('SendQuoteDialog', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('interpolates the template and pre-fills the account recipients', async () => {
    renderSheet(draftQuote.id, '/enviar');

    const subject = await screen.findByLabelText('Asunto');
    await waitFor(() => {
      expect(subject).toHaveValue('Presupuesto P-2026-0001 - Quermed');
    });
    const body = screen.getByLabelText<HTMLTextAreaElement>('Mensaje');
    expect(body.value).toContain('Clínica Tambre');
    expect(screen.getByText('ana@tambre.es')).toBeInTheDocument();
  });

  it('blocks sending without recipients unless sin email is checked', async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API_V1}/quotes/:id/send`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ ...draftQuote, status: 'sent', version: 2 });
      }),
    );
    renderSheet(draftQuote.id, '/enviar');

    await screen.findByLabelText('Asunto');
    const remove = await screen.findByRole('button', { name: /ana@tambre\.es/ });
    await user.click(remove);
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    expect(
      await screen.findByText('Añade al menos un destinatario o marca enviar sin email'),
    ).toBeInTheDocument();
    expect(bodies).toHaveLength(0);

    await user.click(
      screen.getByRole('checkbox', { name: 'Enviar sin email (entrego el PDF yo)' }),
    );
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    await waitFor(() => {
      expect(bodies).toHaveLength(1);
    });
    expect(bodies[0]).toMatchObject({ skip_email: true, recipients: [] });
  });
});

describe('Accept dialog', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('states the consequence and posts the acceptance', async () => {
    const user = userEvent.setup();
    const requests: { body: unknown; ifMatch: string | null }[] = [];
    server.use(
      http.post(`${API_V1}/quotes/:id/accept`, async ({ request }) => {
        requests.push({
          body: await request.json(),
          ifMatch: request.headers.get('if-match'),
        });
        return HttpResponse.json({ ...sentQuote, status: 'accepted' });
      }),
    );
    renderSheet(QUOTE_SENT_ID, '/aceptar');

    expect(await screen.findByText(/Se ganará la oportunidad por 31\.460,00/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Aceptar presupuesto' }));
    await waitFor(() => {
      expect(requests).toHaveLength(1);
    });
    expect(requests[0]?.ifMatch).toBe(`"${String(sentQuote.version)}"`);
  });
});

describe('QuoteSettingsPage', () => {
  it('loads the defaults and saves the PUT payload', async () => {
    sessionStore.getState().setSession('token', adminUser);
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    server.use(
      http.put(`${API_V1}/quote-settings`, async ({ request }) => {
        const body = await request.json();
        bodies.push(body);
        return HttpResponse.json(body);
      }),
    );
    renderRoutes([{ path: '/admin/presupuestos', element: <QuoteSettingsPage /> }], {
      route: '/admin/presupuestos',
    });

    const validity = await screen.findByLabelText('Validez (días)');
    await waitFor(() => {
      expect(validity).toHaveValue('30');
    });
    await user.clear(validity);
    await user.type(validity, '15');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(bodies).toHaveLength(1);
    });
    expect(bodies[0]).toMatchObject({
      conditions_defaults: { validez_dias: 15 },
    });
  });
});
