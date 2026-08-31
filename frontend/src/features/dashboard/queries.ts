import { useQuery } from '@tanstack/react-query';

import { dashboardKeys } from '@/api/query-keys';

import { fetchDashboard } from './api';
import type { DashboardPeriod } from './api';

export function useDashboard(period: DashboardPeriod) {
  return useQuery({
    queryKey: dashboardKeys.panel(period),
    queryFn: () => fetchDashboard(period),
  });
}
