import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';

import '@/styles/globals.css';
import '@/i18n';
import { createQueryClient, Providers } from '@/app/providers';
import { createAppRouter } from '@/app/router';
import { bootstrapSession } from '@/features/auth';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root element not found');
}
const root = createRoot(container);
const queryClient = createQueryClient();

// Turn the refresh cookie into a session before routing so reloads never flash the login page.
void bootstrapSession().finally(() => {
  root.render(
    <StrictMode>
      <Providers queryClient={queryClient}>
        <RouterProvider router={createAppRouter()} />
      </Providers>
    </StrictMode>,
  );
});
