import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { repUser } from '@/test/msw/fixtures';
import { renderWithProviders } from '@/test/render';

import { ContactListPage } from './pages/ContactListPage';

vi.mock('@/hooks/useMediaQuery', () => ({ useIsDesktop: () => false }));

describe('ContactListPage', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  it('lists every visible contact with its centre, specialty and head badge', async () => {
    renderWithProviders(<ContactListPage />);

    const cards = await screen.findByRole('list', { name: 'Contactos' });
    expect(within(cards).getByText('Ana Pérez')).toBeInTheDocument();
    expect(within(cards).getByText('Bea Ruiz')).toBeInTheDocument();
    expect(within(cards).getAllByText('Clínica Tambre')).toHaveLength(2);
    expect(within(cards).getByText('Cirugía Vascular')).toBeInTheDocument();
    expect(within(cards).getByText('Jefe/a de servicio')).toBeInTheDocument();
  });

  it('adds up two specialties, narrows by centre and keeps the rest when a chip is removed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactListPage />);
    await screen.findByText('Ana Pérez');

    // On mobile the controls live in a sheet; the chips stay on the page behind it.
    const pickSpecialty = async (name: string) => {
      await user.click(screen.getByRole('button', { name: 'Filtros' }));
      await user.selectOptions(screen.getByRole('combobox', { name: 'Especialidad' }), name);
      await user.click(screen.getByRole('button', { name: 'Aplicar' }));
    };

    // Ana practises vascular surgery; Bea has no specialty.
    await pickSpecialty('Cirugía Vascular');
    await waitFor(() => {
      expect(screen.queryByText('Bea Ruiz')).not.toBeInTheDocument();
    });
    const chips = screen.getByRole('list', { name: 'Filtros' });
    expect(within(chips).getByText('Cirugía Vascular')).toBeInTheDocument();

    await pickSpecialty('Ginecología');
    await waitFor(() => {
      expect(
        within(screen.getByRole('list', { name: 'Filtros' })).getAllByRole('listitem'),
      ).toHaveLength(2);
    });

    await user.click(screen.getByRole('button', { name: 'Quitar filtro Ginecología' }));
    await waitFor(() => {
      expect(
        within(screen.getByRole('list', { name: 'Filtros' })).getAllByRole('listitem'),
      ).toHaveLength(1);
    });
    expect(screen.getByText('Ana Pérez')).toBeInTheDocument();
  });

  it('reproduces the list from the URL and clears the filters when nothing matches', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ContactListPage />, {
      route: '/contactos?is_head_of_department=true',
    });

    expect(await screen.findByText('Bea Ruiz')).toBeInTheDocument();
    expect(screen.queryByText('Ana Pérez')).not.toBeInTheDocument();

    await user.type(screen.getByRole('searchbox', { name: 'Buscar por nombre' }), 'zzz');
    expect(await screen.findByText('Ningún contacto coincide con los filtros')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Quitar filtros' }));
    expect(await screen.findByText('Ana Pérez')).toBeInTheDocument();
  });
});
