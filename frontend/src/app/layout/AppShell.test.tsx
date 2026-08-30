import { screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { sessionStore } from '@/features/auth';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { renderRoutes } from '@/test/render';

import { AppShell } from './AppShell';

function mockViewport(desktop: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    matches: desktop && query.includes('1024px'),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function renderShell(route = '/hoy') {
  return renderRoutes(
    [
      {
        element: <AppShell />,
        children: [
          { path: '/hoy', element: <h1>Hoy</h1> },
          { path: '/centros', element: <h1>Centros</h1> },
          { path: '/mas', element: <h1>Más</h1> },
          { path: '/admin', element: <h1>Admin</h1> },
        ],
      },
    ],
    { route },
  );
}

describe('AppShell', () => {
  beforeEach(() => {
    sessionStore.getState().setSession('token', repUser);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the bottom navigation with touch-sized targets and the current entry marked', () => {
    mockViewport(false);
    renderShell('/hoy');

    const nav = screen.getAllByRole('navigation', { name: 'Navegación principal' });
    const bottom = nav.find(
      (element) => element.tagName === 'NAV' && element.className.includes('fixed'),
    );
    expect(bottom).toBeDefined();
    const links = within(bottom!).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual([
      'Hoy',
      'Centros',
      'Pipeline',
      'Buscar',
      'Más',
    ]);
    expect(links[0]).toHaveAttribute('aria-current', 'page');
    expect(links[0]?.className).toContain('min-h-touch');
  });

  it('shows the same five entries for every role (Administración lives in Más)', () => {
    mockViewport(false);
    const { unmount } = renderShell();
    expect(screen.queryAllByRole('link', { name: 'Administración' })).toHaveLength(0);
    expect(screen.getAllByRole('link', { name: 'Buscar' }).length).toBeGreaterThan(0);
    unmount();

    sessionStore.getState().setSession('token', adminUser);
    renderShell();
    expect(screen.queryAllByRole('link', { name: 'Administración' })).toHaveLength(0);
    expect(screen.getAllByRole('link', { name: 'Buscar' }).length).toBeGreaterThan(0);
  });

  it('renders the sidebar with the same entries on desktop', () => {
    mockViewport(true);
    sessionStore.getState().setSession('token', adminUser);
    renderShell('/hoy');

    const sidebar = screen.getByRole('complementary');
    const links = within(sidebar).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual([
      'Hoy',
      'Centros',
      'Pipeline',
      'Buscar',
      'Más',
    ]);
  });

  it('shows the offline banner when the browser goes offline', () => {
    mockViewport(false);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    renderShell();

    expect(screen.getByRole('status')).toHaveTextContent('Sin conexión');
  });
});
