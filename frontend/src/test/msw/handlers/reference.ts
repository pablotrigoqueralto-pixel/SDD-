import { http, HttpResponse } from 'msw';

import { API_V1 } from '../constants';
import { divisions, page, territories } from '../fixtures';

export const referenceHandlers = [
  http.get(`${API_V1}/divisions`, () => HttpResponse.json(divisions)),
  http.get(`${API_V1}/territories`, () => HttpResponse.json(page(territories))),
];
