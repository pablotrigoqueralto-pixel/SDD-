import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type ContactRead = components['schemas']['ContactRead'];
export type ContactCreate = components['schemas']['ContactCreate'];
export type ContactUpdate = components['schemas']['ContactUpdate'];
export type ConsentWrite = components['schemas']['ConsentWrite'];
export type ConsentStatus = components['schemas']['ConsentStatus'];
export type ConsentSource = components['schemas']['ConsentSource'];
export type PreferredChannel = components['schemas']['PreferredChannel'];
export type ContactSummaryRead = components['schemas']['ContactSummaryRead'];
export type ContactPage = components['schemas']['Page_ContactSummaryRead_'];

/** Repeated ids add up (OR); different filters narrow (AND) — same rule as the API. */
export interface ContactListFilters {
  q?: string;
  specialty_id?: string[];
  account_id?: string[];
  job_title_id?: string;
  is_head_of_department?: boolean;
  is_active?: boolean | null;
  sort?: string;
  page?: number;
  page_size?: number;
}

export async function listContacts(filters: ContactListFilters): Promise<ContactPage> {
  type ParamValue = string | number | boolean | string[];
  const params: Record<string, ParamValue> = {};
  const entries = Object.entries(filters) as [string, ParamValue | null | undefined][];
  for (const [key, value] of entries) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value) && value.length === 0) continue;
    params[key] = value;
  }
  const { data } = await apiClient.get<ContactPage>('/contacts', {
    params,
    // Repeatable filters travel as `specialty_id=a&specialty_id=b`; axios would
    // otherwise send `specialty_id[]=`, which FastAPI does not read as a list.
    paramsSerializer: { indexes: null },
  });
  return data;
}

export async function listAccountContacts(
  accountId: string,
  includeInactive = false,
): Promise<ContactRead[]> {
  const { data } = await apiClient.get<ContactRead[]>(`/accounts/${accountId}/contacts`, {
    params: includeInactive ? { include_inactive: true } : {},
  });
  return data;
}

export async function getContact(id: string): Promise<ContactRead> {
  const { data } = await apiClient.get<ContactRead>(`/contacts/${id}`);
  return data;
}

export async function createContact(
  accountId: string,
  payload: ContactCreate,
): Promise<ContactRead> {
  const { data } = await apiClient.post<ContactRead>(`/accounts/${accountId}/contacts`, payload);
  return data;
}

export async function updateContact(
  id: string,
  version: number,
  payload: ContactUpdate,
): Promise<ContactRead> {
  const { data } = await apiClient.patch<ContactRead>(`/contacts/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function anonymiseContact(id: string, version: number): Promise<ContactRead> {
  const { data } = await apiClient.post<ContactRead>(`/contacts/${id}/anonymise`, null, {
    headers: ifMatch(version),
  });
  return data;
}
