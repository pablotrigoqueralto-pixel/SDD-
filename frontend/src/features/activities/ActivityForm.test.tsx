import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { tambre } from '@/test/msw/accounts-fixtures';
import {
  CALL_TYPE_ID,
  NOTE_TYPE_ID,
  VISIT_TYPE_ID,
  visitDone,
} from '@/test/msw/activities-fixtures';
import { adminUser, problem, repUser } from '@/test/msw/fixtures';
import { API_V1 } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderWithProviders } from '@/test/render';

import { ActivityForm } from './components/ActivityForm';
import { ActivityTypePicker } from './components/ActivityTypePicker';

describe('ActivityTypePicker', () => {
  it('is a keyboard-operable radio group with the master icons', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<ActivityTypePicker name="t" value="" onChange={onChange} />);

    const group = await screen.findByRole('group', { name: 'Tipo de actividad' });
    const radios = await within(group).findAllByRole('radio');
    expect(radios.map((radio) => radio.parentElement?.textContent)).toEqual([
      'Visita',
      'Llamada',
      'Nota',
    ]);
    await user.click(within(group).getByRole('radio', { name: 'Llamada' }));
    expect(onChange).toHaveBeenCalledWith(CALL_TYPE_ID);
  });
});

describe('ActivityForm', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('records a visit in two taps with the primary contact pre-checked', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/activities`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...visitDone, id: 'created' }, { status: 201 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<ActivityForm account={tambre} onSaved={onSaved} />);

    await user.click(await screen.findByRole('radio', { name: 'Visita' }));
    expect(screen.getByRole('button', { name: 'Más datos (opcional)' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    await user.click(screen.getByRole('button', { name: 'Más datos (opcional)' }));
    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: 'Ana Pérez' })).toBeChecked();
    });
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(body).toMatchObject({
      account_id: tambre.id,
      activity_type_id: VISIT_TYPE_ID,
      status: 'done',
      contact_ids: ['019000000-0000-7000-8000-0000000000k1'],
    });
    expect(typeof body.scheduled_at).toBe('string');
  });

  it('plans with tomorrow 09:00 by default, disables planning for notes, sends a next action', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_V1}/activities`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...visitDone, id: 'created' }, { status: 201 });
      }),
    );
    renderWithProviders(<ActivityForm account={tambre} onSaved={vi.fn()} />);

    await user.click(await screen.findByRole('radio', { name: 'Nota' }));
    expect(screen.getByRole('radio', { name: 'Planificada' })).toBeDisabled();
    expect(screen.getByRole('note')).toHaveTextContent('Las notas se registran, no se planifican');

    await user.click(screen.getByRole('radio', { name: 'Llamada' }));
    await user.click(screen.getByRole('radio', { name: 'Planificada' }));
    const when = screen.getByLabelText<HTMLInputElement>('Fecha y hora');
    expect(when.value.endsWith('T09:00')).toBe(true);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    expect(when.value.slice(8, 10)).toBe(String(tomorrow.getDate()).padStart(2, '0'));

    await user.click(screen.getByRole('button', { name: 'Más datos (opcional)' }));
    expect(screen.queryByLabelText('Resultado')).not.toBeInTheDocument(); // planned: no outcome
    await user.selectOptions(screen.getByRole('combobox', { name: 'Tipo' }), 'Visita');
    await user.type(screen.getByLabelText('Cuándo'), '2030-01-15T10:00');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(body.status).toBe('planned');
    });
    expect(body.next_action).toMatchObject({ activity_type_id: VISIT_TYPE_ID });
    expect((body.next_action as { scheduled_at: string }).scheduled_at).toContain('2030');
    expect(body.activity_type_id).toBe(CALL_TYPE_ID);
    expect(body.activity_type_id).not.toBe(NOTE_TYPE_ID);
  });

  it('shows the owner selector to managers and inline backend errors', async () => {
    const user = userEvent.setup();
    sessionStore.getState().setSession('token', { ...adminUser, role: 'sales_manager' });
    server.use(
      http.post(`${API_V1}/activities`, () =>
        problem(422, 'contact_not_in_account', 'bad', [
          { field: 'contact_ids', message: 'bad', code: 'contact_not_in_account' },
        ]),
      ),
    );
    renderWithProviders(<ActivityForm account={tambre} onSaved={vi.fn()} />);

    await user.click(await screen.findByRole('radio', { name: 'Visita' }));
    await user.click(screen.getByRole('button', { name: 'Más datos (opcional)' }));
    expect(screen.getByRole('combobox', { name: 'Comercial' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(
      await screen.findByText('Alguno de los contactos no pertenece a este centro'),
    ).toBeInTheDocument();
  });

  it('edits sending only changed descriptive fields with the version', async () => {
    const user = userEvent.setup();
    let ifMatch: string | null = null;
    let body: Record<string, unknown> = {};
    server.use(
      http.patch(`${API_V1}/activities/:id`, async ({ request }) => {
        ifMatch = request.headers.get('if-match');
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...visitDone, ...body, version: 2 });
      }),
    );
    const onSaved = vi.fn();
    renderWithProviders(<ActivityForm account={tambre} activity={visitDone} onSaved={onSaved} />);

    expect(screen.queryByRole('radio', { name: 'Planificada' })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText('Asunto'));
    await user.type(screen.getByLabelText('Asunto'), 'Demo ecógrafo');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Resultado' }), 'Neutra');
    await user.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalled();
    });
    expect(ifMatch).toBe('"1"');
    expect(body).toEqual({ subject: 'Demo ecógrafo', outcome: 'neutral' });
  });
});
