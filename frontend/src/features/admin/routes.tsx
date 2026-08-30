import { Route, Routes } from 'react-router-dom';

import { QuoteSettingsPage } from '@/features/quotes';

import { BrandFormRoute } from './brands/pages/BrandFormRoute';
import { BrandListPage } from './brands/pages/BrandListPage';
import { JobTitleFormRoute, JobTitleListPage } from './job-titles/pages/JobTitleListPage';
import { LossReasonFormRoute, LossReasonListPage } from './loss-reasons/pages/LossReasonListPage';
import { AdminHubPage } from './pages/AdminHubPage';
import { PipelinesPage } from './pipelines/pages/PipelinesPage';
import {
  ProductFamilyFormRoute,
  ProductFamilyListPage,
} from './product-families/pages/ProductFamilyListPage';
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
      <Route path="cargos" element={<JobTitleListPage />}>
        <Route path="nuevo" element={<JobTitleFormRoute />} />
        <Route path=":jobTitleId" element={<JobTitleFormRoute />} />
      </Route>
      <Route path="familias" element={<ProductFamilyListPage />}>
        <Route path="nueva" element={<ProductFamilyFormRoute />} />
        <Route path=":familyId" element={<ProductFamilyFormRoute />} />
      </Route>
      <Route path="presupuestos" element={<QuoteSettingsPage />} />
    </Routes>
  );
}
