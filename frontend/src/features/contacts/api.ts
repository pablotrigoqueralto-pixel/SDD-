import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type ContactRead = components['schemas']['ContactRead'];
export type ContactCreate = components['schemas']['ContactCreate'];
export type ContactUpdate = components['schemas']['ContactUpdate'];
export type ConsentWrite = components['schemas']['ConsentWrite'];
export type ConsentStatus = components['schemas']['ConsentStatus'];
export type ConsentSource = components['schemas']['ConsentSource'];
export type PreferredChannel = components['schemas']['PreferredChannel'];

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
