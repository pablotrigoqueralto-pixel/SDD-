import { Route, Routes } from 'react-router-dom';

import { CatalogueListPage } from './pages/CatalogueListPage';
import { ProductFormRoute } from './pages/ProductFormRoute';

/** Mounted under /catalogo/* for every authenticated role (writes gated inside the form). */
export function CatalogueRoutes() {
  return (
    <Routes>
      <Route path="/" element={<CatalogueListPage />}>
        <Route path="nuevo" element={<ProductFormRoute />} />
        <Route path=":productId" element={<ProductFormRoute />} />
      </Route>
    </Routes>
  );
}
