import type { RequestHandler } from 'msw';

import { accountHandlers } from './accounts';
import { activityHandlers } from './activities';
import { adminHandlers } from './admin';
import { authHandlers } from './auth';
import { catalogueHandlers } from './catalogue';
import { opportunityHandlers } from './opportunities';
import { quoteHandlers } from './quotes';
import { referenceHandlers } from './reference';
import { searchImportHandlers } from './search-imports';

export { API_URL, API_V1 } from '../constants';

/** Default handlers reflecting api-spec.yml; tests override per case with server.use(). */
export const handlers: RequestHandler[] = [
  ...authHandlers,
  ...referenceHandlers,
  ...adminHandlers,
  ...accountHandlers,
  ...activityHandlers,
  ...catalogueHandlers,
  ...opportunityHandlers,
  ...quoteHandlers,
  ...searchImportHandlers,
];
