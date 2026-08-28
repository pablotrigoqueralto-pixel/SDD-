import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { renderRoutes } from '@/test/render';

import { AdminHubPage } from './AdminHubPage';

describe('AdminHubPage', () => {
  it('shows two large cards that navigate to users and territories', async () => {
    const user = userEvent.setup();
    renderRoutes(
      [
        { path: '/admin', element: <AdminHubPage /> },
        { path: '/admin/usuarios', element: <h1>Usuarios page</h1> },
        { path: '/admin/territorios', element: <h1>Territorios page</h1> },
      ],
      { route: '/admin' },
    );

    const links = screen.getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual([
      'UsuariosAltas, roles, territorios y divisiones',
      'TerritoriosProvincias que cubre cada territorio',
      'MarcasFabricantes propios y competencia',
      'Motivos de pérdidaPor qué se pierden oportunidades',
      'PipelinesEtapas y probabilidades',
    ]);
    await user.click(links[1]!);

    expect(await screen.findByText('Territorios page')).toBeInTheDocument();
  });
});
