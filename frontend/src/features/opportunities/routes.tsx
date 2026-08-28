import { Route, Routes } from 'react-router-dom';

import { OpportunityPage } from './pages/OpportunityPage';
import { OpportunityDialogRoute, OpportunityNewRoute } from './pages/OpportunityRoutes';
import { PipelinePage } from './pages/PipelinePage';

/** Mounted under /oportunidades/* for every authenticated role. */
export function OpportunityRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PipelinePage />}>
        <Route path="nueva" element={<OpportunityNewRoute />} />
      </Route>
      <Route path=":opportunityId" element={<OpportunityPage />}>
        <Route path="editar" element={<OpportunityDialogRoute kind="edit" />} />
        <Route path="ganar" element={<OpportunityDialogRoute kind="win" />} />
        <Route path="perder" element={<OpportunityDialogRoute kind="lose" />} />
      </Route>
    </Routes>
  );
}
