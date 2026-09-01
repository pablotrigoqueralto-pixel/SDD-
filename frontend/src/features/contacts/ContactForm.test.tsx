import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { ana, bea, tambre } from '@/test/msw/accounts-fixtures';
import { adminUser, problem, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { referenceBundle } from '@/test/msw/reference-fixtures';
import { server } from '@/test/msw/server';
import { renderWithProviders } from '@/test/render';

import { ContactForm } from './components/ContactForm';

describe('ContactForm', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('creates with two fields, picks a catalogue specialty and fills the job title from the bundle', async () => {
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
    const specialty = screen.getByRole('combobox', { name: 'Especialidad' });
    expect(specialty).toHaveValue(''); // no specialty is guessed from the centre
    expect(within(specialty).getByRole('option', { name: 'Cirugía Vascular' })).toBeInTheDocument();
    expect(within(specialty).queryByRole('option', { name: 'Consumibles' })).toBeNull();
    expect(screen.getByRole('radio', { name: 'Teléfono' })).toBeDisabled();

    await user.type(screen.getByLabelText('Nombre'), 'Carla');
    await user.type(screen.getByLabelText('Apellidos'), 'Gómez');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Cargo' }), 'Ginecólogo/a');
    await user.selectOptions(specialty, 'Cirugía Vascular');
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
      specialty_id: '019000000-0000-7000-8000-0000000000s2',
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

  it('lets an admin add a missing specialty without losing the form', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', adminUser);
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/specialties`, () =>
        HttpResponse.json(
          { id: 'new-specialty', name_es: 'Urología', outcome: 'created' },
          { status: 201 },
        ),
      ),
      http.get(`${API_V1}/reference-data`, () =>
        HttpResponse.json({
          ...referenceBundle,
          specialties: [
            ...referenceBundle.specialties,
            {
              id: 'new-specialty',
              code: 'urologia',
              name_es: 'Urología',
              sort_order: 130,
              is_active: true,
              version: 1,
              created_at: null,
              updated_at: null,
            },
          ],
        }),
      ),
      http.post(`${API_V1}/accounts/:id/contacts`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...bea, id: 'created' }, { status: 201 });
      }),
    );
    renderWithProviders(<ContactForm account={tambre} onSaved={vi.fn()} />);

    await user.type(await screen.findByLabelText('Nombre'), 'Elena');
    await user.type(screen.getByLabelText('Apellidos'), 'Ruiz');
    await user.click(screen.getAllByRole('button', { name: '+ Añadir' })[1]!);
    // "Nombre" also labels the contact's own field: stay inside the dialog.
    const dialog = within(screen.getByRole('dialog'));
    await user.type(dialog.getByLabelText('Nombre'), 'Urología');
    await user.click(dialog.getByRole('button', { name: 'Guardar' }));

    // The dialog closed with the entry selected; the half-filled form survived.
    // The bundle refetches, so the option exists before the value can stick.
    expect(await screen.findByRole('option', { name: 'Urología' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Especialidad' })).toHaveValue('new-specialty');
    });
    expect(screen.getByLabelText('Apellidos')).toHaveValue('Ruiz');

    await user.click(screen.getByRole('button', { name: 'Guardar' }));
    await waitFor(() => {
      expect(body.specialty_id).toBe('new-specialty');
    });
  });

  it('offers no add buttons to a sales rep', async () => {
    renderWithProviders(<ContactForm account={tambre} onSaved={vi.fn()} />);

    expect(await screen.findByRole('combobox', { name: 'Cargo' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '+ Añadir' })).not.toBeInTheDocument();
  });
});
