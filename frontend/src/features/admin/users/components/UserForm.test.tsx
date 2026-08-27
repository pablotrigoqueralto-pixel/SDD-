import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useConflictStore } from '@/store/conflict.store';
import { CENTRO_ID, VASCULAR_ID, problem, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderWithProviders } from '@/test/render';

import { UserForm } from './UserForm';

afterEach(() => {
  useConflictStore.getState().dismiss();
});

describe('UserForm (create)', () => {
  it('creates a user with scope and reports success', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/users`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...repUser, id: 'created' }, { status: 201 });
      }),
    );
    renderWithProviders(<UserForm onSaved={onSaved} />);
    await screen.findByLabelText('Centro');

    await user.type(screen.getByLabelText('Nombre completo'), 'Nueva Comercial');
    await user.type(screen.getByLabelText('Email'), 'Nueva@Quermed.com');
    await user.selectOptions(screen.getByLabelText('Rol'), 'sales_rep');
    await user.click(screen.getByLabelText('Centro'));
    await user.click(screen.getByLabelText('Vascular'));
    await user.type(screen.getByLabelText('Contraseña'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toMatchObject({
      email: 'Nueva@Quermed.com',
      full_name: 'Nueva Comercial',
      role: 'sales_rep',
      territory_ids: [CENTRO_ID],
      division_ids: [VASCULAR_ID],
      password: 'correct-horse-battery',
    });
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });

  it('warns when a sales rep has no territory or division but still allows saving', async () => {
    renderWithProviders(<UserForm onSaved={vi.fn()} />);

    expect(await screen.findByRole('note')).toHaveTextContent(
      'Un comercial sin territorio o división no verá ningún centro',
    );
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeEnabled();
  });

  it('shows the duplicate email error under the email field', async () => {
    const user = userEvent.setup();
    server.use(http.post(`${API_V1}/users`, () => problem(409, 'email_already_exists', 'exists')));
    renderWithProviders(<UserForm onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText('Nombre completo'), 'Ana');
    await user.type(screen.getByLabelText('Email'), 'ana@quermed.com');
    await user.type(screen.getByLabelText('Contraseña'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Ya existe un usuario con este email')).toBeInTheDocument();
  });

  it('maps backend field errors and validates the password length locally', async () => {
    const user = userEvent.setup();
    renderWithProviders(<UserForm onSaved={vi.fn()} />);

    await user.type(screen.getByLabelText('Nombre completo'), 'Ana');
    await user.type(screen.getByLabelText('Email'), 'ana@quermed.com');
    await user.type(screen.getByLabelText('Contraseña'), 'short');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(
      await screen.findByText('La contraseña debe tener al menos 12 caracteres'),
    ).toBeInTheDocument();
  });
});

describe('UserForm (edit)', () => {
  it('sends only editable fields with the version and offers a password reset', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    let ifMatch: string | null = null;
    server.use(
      http.patch(`${API_V1}/users/:id`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...repUser, ...body, version: 2 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<UserForm user={{ ...repUser, version: 7 }} onSaved={onSaved} />);
    await screen.findByLabelText('Centro');

    expect(screen.getByLabelText('Email')).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Restablecer contraseña' }));
    await user.type(screen.getByLabelText('Nueva contraseña'), 'another-passphrase');
    await user.click(screen.getByLabelText('Activo'));
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(ifMatch).toBe('"7"');
    expect(body).toMatchObject({ is_active: false, password: 'another-passphrase' });
    expect(body).not.toHaveProperty('email');
  });

  it('opens the conflict dialog on 409', async () => {
    const user = userEvent.setup();
    server.use(http.patch(`${API_V1}/users/:id`, () => problem(409, 'conflict', 'stale')));
    renderWithProviders(<UserForm user={repUser} onSaved={vi.fn()} />);
    await screen.findByLabelText('Centro');

    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(useConflictStore.getState().open).toBe(true);
    });
  });
});
