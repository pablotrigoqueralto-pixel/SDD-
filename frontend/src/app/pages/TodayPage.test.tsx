import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { sessionStore } from '@/store/session.store';
import { adminUser, repUser } from '@/test/msw/fixtures';
import { renderWithProviders } from '@/test/render';

import { TodayPage } from './TodayPage';

describe('TodayPage', () => {
  it('warns a sales rep without territory or division', () => {
    sessionStore.getState().setSession('t', { ...repUser, division_ids: [] });
    renderWithProviders(<TodayPage />);

    expect(screen.getByRole('note')).toHaveTextContent(
      'Sin territorio o división asignados; contacta con administración',
    );
  });

  it('shows no warning for a rep with scope or for other roles', () => {
    sessionStore.getState().setSession('t', repUser);
    const { unmount } = renderWithProviders(<TodayPage />);
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
    unmount();

    sessionStore.getState().setSession('t', adminUser);
    renderWithProviders(<TodayPage />);
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });
});
