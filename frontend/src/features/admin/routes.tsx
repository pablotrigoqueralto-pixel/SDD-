import { Route, Routes } from 'react-router-dom';

import { AdminHubPage } from './pages/AdminHubPage';
import { TerritoryFormRoute } from './territories/pages/TerritoryFormRoute';
import { TerritoryListPage } from './territories/pages/TerritoryListPage';
import { UserFormRoute } from './users/pages/UserFormRoute';
import { UserListPage } from './users/pages/UserListPage';

/** Mounted under /admin/* (admin role only). Forms render over their list via nested routes. */
export function AdminRoutes() {
  return (
    <Routes>
      <Route index element={<AdminHubPage />} />
      <Route path="usuarios" element={<UserListPage />}>
        <Route path="nuevo" element={<UserFormRoute />} />
        <Route path=":userId" element={<UserFormRoute />} />
      </Route>
      <Route path="territorios" element={<TerritoryListPage />}>
        <Route path="nuevo" element={<TerritoryFormRoute />} />
        <Route path=":territoryId" element={<TerritoryFormRoute />} />
      </Route>
    </Routes>
  );
}
