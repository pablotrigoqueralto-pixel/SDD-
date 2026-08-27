import { refreshAccessToken } from '@/api/client';
import { sessionStore } from '@/store/session.store';

/**
 * Called once before the router mounts: turn the refresh cookie into an access token
 * so a reload never flashes the login page for a signed-in user.
 */
export async function bootstrapSession(): Promise<void> {
  if (sessionStore.getState().status !== 'unknown') {
    return;
  }
  const token = await refreshAccessToken();
  if (!token) {
    sessionStore.getState().clear();
  }
}
