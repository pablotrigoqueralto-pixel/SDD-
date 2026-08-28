import { Route, Routes } from 'react-router-dom';

import { BrandFormRoute } from './brands/pages/BrandFormRoute';
import { BrandListPage } from './brands/pages/BrandListPage';
import { LossReasonFormRoute, LossReasonListPage } from './loss-reasons/pages/LossReasonListPage';
import { AdminHubPage } from './pages/AdminHubPage';
import { PipelinesPage } from './pipelines/pages/PipelinesPage';
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
      <Route path="marcas" element={<BrandListPage />}>
        <Route path="nueva" element={<BrandFormRoute />} />
        <Route path=":brandId" element={<BrandFormRoute />} />
      </Route>
      <Route path="motivos-perdida" element={<LossReasonListPage />}>
        <Route path="nuevo" element={<LossReasonFormRoute />} />
        <Route path=":reasonId" element={<LossReasonFormRoute />} />
      </Route>
      <Route path="pipelines" element={<PipelinesPage />} />
    </Routes>
  );
}
