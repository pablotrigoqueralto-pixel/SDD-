import { Route, Routes } from 'react-router-dom';

import { ActivityDetailRoute, ActivityNewRoute, TimelinePage } from '@/features/activities';
import { ContactFormRoute } from '@/features/contacts';
import { OpportunityNewRoute } from '@/features/opportunities';

import { AccountCreateRoute, AccountDialogRoute } from './pages/AccountFormRoute';
import { AccountListPage } from './pages/AccountListPage';
import { AccountPage } from './pages/AccountPage';

/** Mounted under /centros/* for every authenticated role. */
export function AccountRoutes() {
  return (
    <Routes>
      <Route index element={<AccountListPage />} />
      <Route path="nuevo" element={<AccountListPage />}>
        <Route index element={<AccountCreateRoute />} />
      </Route>
      <Route path=":accountId" element={<AccountPage />}>
        <Route path="editar" element={<AccountDialogRoute kind="edit" />} />
        <Route path="direcciones" element={<AccountDialogRoute kind="addresses" />} />
        <Route path="asignar" element={<AccountDialogRoute kind="assign" />} />
        <Route path="contactos/nuevo" element={<ContactFormRoute />} />
        <Route path="contactos/:contactId/editar" element={<ContactFormRoute />} />
        <Route path="actividades/nueva" element={<ActivityNewRoute />} />
        <Route path="oportunidades/nueva" element={<OpportunityNewRoute />} />
        <Route path="actividades/:activityId" element={<ActivityDetailRoute />} />
      </Route>
      <Route path=":accountId/actividades" element={<TimelinePage />} />
    </Routes>
  );
}
