import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { API_V1 } from '@/test/msw/constants';
import { adminUser, problem, repUser } from '@/test/msw/fixtures';
import { server } from '@/test/msw/server';
import { renderWithProviders } from '@/test/render';

import { CreateOptionDialog } from './CreateOptionDialog';

describe('CreateOptionDialog', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', adminUser);
  });

  it('creates the entry and hands it back selected', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/specialties`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: 'new-specialty', name_es: 'Urología', outcome: 'created' },
          { status: 201 },
        );
      }),
    );
    const onCreated = vi.fn();
    renderWithProviders(<CreateOptionDialog kind="specialty" onCreated={onCreated} />);

    await user.click(screen.getByRole('button', { name: '+ Añadir' }));
    await user.type(screen.getByLabelText('Nombre'), 'Urología');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith('new-specialty');
    });
    expect(body).toEqual({ name: 'Urología' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('says when the entry already existed or came back, and still selects it', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API_V1}/job-titles`, () =>
        HttpResponse.json(
          { id: 'existing', name_es: 'Gerencia', outcome: 'reactivated' },
          { status: 201 },
        ),
      ),
    );
    const onCreated = vi.fn();
    renderWithProviders(<CreateOptionDialog kind="job_title" onCreated={onCreated} />);

    await user.click(screen.getByRole('button', { name: '+ Añadir' }));
    await user.type(screen.getByLabelText('Nombre'), 'gerencia');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith('existing');
    });
    expect(await screen.findByText(/Ya existía desactivado/)).toBeInTheDocument();
  });

  it('asks for the tender flag when the catalogue is account types', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/account-types`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: 'new-type', name_es: 'Consorcio sanitario', outcome: 'created' },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<CreateOptionDialog kind="account_type" onCreated={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: '+ Añadir' }));
    await user.type(screen.getByLabelText('Nombre'), 'Consorcio sanitario');
    await user.click(screen.getByLabelText('Compra por licitación'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(body).toEqual({ name: 'Consorcio sanitario', buys_via_tender: true });
    });
  });

  it('keeps a backend error inside the dialog', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${API_V1}/specialties`, () =>
        problem(422, 'validation_error', 'Nombre no válido'),
      ),
    );
    const onCreated = vi.fn();
    renderWithProviders(<CreateOptionDialog kind="specialty" onCreated={onCreated} />);

    await user.click(screen.getByRole('button', { name: '+ Añadir' }));
    await user.type(screen.getByLabelText('Nombre'), '...');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('is invisible to anyone who is not an administrator', () => {
    sessionStore.getState().setSession('token', repUser);

    renderWithProviders(<CreateOptionDialog kind="specialty" onCreated={vi.fn()} />);

    expect(screen.queryByRole('button', { name: '+ Añadir' })).not.toBeInTheDocument();
  });

  it('closes with Escape and gives the focus back to the button', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateOptionDialog kind="specialty" onCreated={vi.fn()} />);
    const trigger = screen.getByRole('button', { name: '+ Añadir' });

    await user.click(trigger);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    // The name field is labelled, so a screen reader announces what is being typed.
    expect(screen.getByLabelText('Nombre')).toBeInTheDocument();

    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(trigger).toHaveFocus();
  });
});
