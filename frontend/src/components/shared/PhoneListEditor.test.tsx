import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { PhoneListEditor, toPhonePayload, type PhoneInput } from './PhoneListEditor';

function Harness({ initial = [] as PhoneInput[] }) {
  const [phones, setPhones] = useState<PhoneInput[]>(initial);
  return (
    <>
      <PhoneListEditor value={phones} onChange={setPhones} />
      <output data-testid="payload">{JSON.stringify(toPhonePayload(phones))}</output>
    </>
  );
}

const CENTRALITA: PhoneInput = {
  label: 'Centralita',
  number: '915550000',
  extension: '',
  note: '',
};
const SECRETARIA: PhoneInput = {
  label: 'Secretaría',
  number: '915550001',
  extension: '4021',
  note: '',
};

function payload(): unknown {
  return JSON.parse(screen.getByTestId('payload').textContent);
}

describe('PhoneListEditor', () => {
  it('adds a row with a free label and an extension', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);

    expect(screen.getByText('Sin teléfonos todavía')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Añadir teléfono' }));

    // The label input offers suggestions, so its role is combobox.
    await user.type(screen.getByRole('combobox', { name: 'Etiqueta' }), 'Planta 3 · box 2');
    await user.type(screen.getByRole('textbox', { name: 'Número' }), '915550009');
    await user.type(screen.getByRole('textbox', { name: 'Extensión' }), '4021');

    expect(payload()).toEqual([
      { label: 'Planta 3 · box 2', number: '915550009', extension: '4021' },
    ]);
  });

  it('makes a row primary by moving it to the front', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[CENTRALITA, SECRETARIA]} />);

    const rows = screen.getAllByRole('listitem');
    await user.click(within(rows[1]!).getByRole('button', { name: 'Hacer principal' }));

    expect(payload()).toEqual([
      { label: 'Secretaría', number: '915550001', extension: '4021' },
      { label: 'Centralita', number: '915550000' },
    ]);
  });

  it('removes a row', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[CENTRALITA, SECRETARIA]} />);

    await user.click(screen.getByRole('button', { name: 'Quitar teléfono Centralita' }));

    expect(payload()).toEqual([{ label: 'Secretaría', number: '915550001', extension: '4021' }]);
  });

  it('marks the first row as the primary one', () => {
    renderWithProviders(<Harness initial={[CENTRALITA, SECRETARIA]} />);

    const rows = screen.getAllByRole('listitem');
    expect(within(rows[0]!).getByText(/Principal/)).toBeInTheDocument();
    expect(within(rows[1]!).queryByText(/Principal/)).not.toBeInTheDocument();
  });

  it('drops incomplete rows from the payload', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[CENTRALITA]} />);

    await user.click(screen.getByRole('button', { name: 'Añadir teléfono' }));

    expect(payload()).toEqual([{ label: 'Centralita', number: '915550000' }]);
  });
});
