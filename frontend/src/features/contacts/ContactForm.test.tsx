import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { ana, bea, tambre } from '@/test/msw/accounts-fixtures';
import { problem, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderWithProviders } from '@/test/render';

import { ContactForm } from './components/ContactForm';

describe('ContactForm', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('creates with two fields, defaults the speciality and fills the job title from the bundle', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/accounts/:id/contacts`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...bea, id: 'created' }, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<ContactForm account={tambre} onSaved={onSaved} />);

    expect(await screen.findByRole('option', { name: 'Ginecólogo/a' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Otro' })).not.toBeInTheDocument(); // inactive
    expect(screen.getByRole('combobox', { name: 'Especialidad' })).toHaveValue(
      '019000000-0000-7000-8000-0000000000d1',
    );
    expect(screen.getByRole('radio', { name: 'Teléfono' })).toBeDisabled();

    await user.type(screen.getByLabelText('Nombre'), 'Carla');
    await user.type(screen.getByLabelText('Apellidos'), 'Gómez');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Cargo' }), 'Ginecólogo/a');
    await user.click(screen.getByRole('button', { name: 'Añadir teléfono' }));
    await user.type(screen.getByRole('combobox', { name: 'Etiqueta' }), 'Móvil');
    await user.type(screen.getByRole('textbox', { name: 'Número' }), '612 345 678');
    await user.click(screen.getByRole('radio', { name: 'Teléfono' }));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toEqual({
      first_name: 'Carla',
      last_name: 'Gómez',
      is_primary: false,
      job_title_id: '019000000-0000-7000-8000-0000000000j1',
      division_id: '019000000-0000-7000-8000-0000000000d1',
      phones: [{ label: 'Móvil', number: '612 345 678' }],
      preferred_channel: 'phone',
    });
  });

  it('defaults the consent date to today when the status changes and requires the source', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/accounts/:id/contacts`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...bea, id: 'created' }, { status: 201 });
      }),
    );
    renderWithProviders(<ContactForm account={tambre} onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText('Nombre'), 'Carla');
    await user.type(screen.getByLabelText('Apellidos'), 'Gómez');
    expect(screen.getByLabelText('Fecha')).toBeDisabled();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Estado' }), 'Concedido');
    expect(screen.getByLabelText('Fecha')).toHaveValue(new Date().toISOString().slice(0, 10));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Indica el origen del consentimiento')).toBeInTheDocument();

    await user.selectOptions(screen.getByRole('combobox', { name: 'Origen' }), 'Verbal');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(body.consent).toMatchObject({ status: 'granted', source: 'verbal' });
    });
  });

  it('edits sending only the changes with the version and shows backend errors inline', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    server.use(
      http.patch(`${API_V1}/contacts/:id`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        // Mirrors the backend rule: the phone channel needs at least one number.
        const channel = body.preferred_channel ?? ana.preferred_channel;
        if (channel === 'phone' && Array.isArray(body.phones) && body.phones.length === 0) {
          return problem(422, 'preferred_channel_missing_value', 'missing', [
            {
              field: 'preferred_channel',
              message: 'missing',
              code: 'preferred_channel_missing_value',
            },
          ]);
        }
        return HttpResponse.json({ ...ana, ...body, version: 2 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<ContactForm account={tambre} contact={ana} onSaved={onSaved} />);

    expect(screen.getByLabelText('Nombre')).toHaveValue('Ana');
    // Ana prefers the phone channel: removing her only number must be rejected.
    await user.click(screen.getByRole('button', { name: /Quitar teléfono/ }));
    await user.click(screen.getByLabelText('Contacto principal'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('El canal preferido no tiene ningún dato')).toBeInTheDocument();
    expect(ifMatch).toBe('"1"');
    expect(body).toEqual({ phones: [], is_primary: false });

    await user.click(screen.getByRole('radio', { name: 'Email' }));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));
    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
  });
});
