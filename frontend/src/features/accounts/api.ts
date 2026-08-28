import { apiClient, ifMatch } from '@/api/client';
import type { components, operations } from '@/api/schema';

export type AccountRead = components['schemas']['AccountRead'];
export type AccountSummaryRead = components['schemas']['AccountSummaryRead'];
export type AccountCreate = components['schemas']['AccountCreate'];
export type AccountUpdate = components['schemas']['AccountUpdate'];
export type AccountAssignment = components['schemas']['AccountAssignment'];
export type AddressWrite = components['schemas']['AddressWrite'];
export type AccountPage = components['schemas']['Page_AccountSummaryRead_'];
export type AccountListQuery = NonNullable<
  operations['list_accounts_api_v1_accounts_get']['parameters']['query']
>;

export interface AccountListFilters {
  q?: string;
  account_type_id?: string;
  territory_id?: string;
  owner_id?: string;
  division_id?: string;
  is_active?: boolean | null;
  unassigned?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}

export async function listAccounts(filters: AccountListFilters): Promise<AccountPage> {
  const params: Record<string, string | number | boolean> = {};
  const entries = Object.entries(filters) as [
    string,
    string | number | boolean | null | undefined,
  ][];
  for (const [key, value] of entries) {
    if (value !== undefined && value !== '' && value !== null) params[key] = value;
  }
  const { data } = await apiClient.get<AccountPage>('/accounts', { params });
  return data;
}

export async function getAccount(id: string): Promise<AccountRead> {
  const { data } = await apiClient.get<AccountRead>(`/accounts/${id}`);
  return data;
}

export async function createAccount(payload: AccountCreate): Promise<AccountRead> {
  const { data } = await apiClient.post<AccountRead>('/accounts', payload);
  return data;
}

export async function updateAccount(
  id: string,
  version: number,
  payload: AccountUpdate,
): Promise<AccountRead> {
  const { data } = await apiClient.patch<AccountRead>(`/accounts/${id}`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function assignAccount(
  id: string,
  version: number,
  payload: AccountAssignment,
): Promise<AccountRead> {
  const { data } = await apiClient.put<AccountRead>(`/accounts/${id}/assignment`, payload, {
    headers: ifMatch(version),
  });
  return data;
}

export async function replaceAddresses(
  id: string,
  version: number,
  addresses: AddressWrite[],
): Promise<AccountRead> {
  const { data } = await apiClient.put<AccountRead>(
    `/accounts/${id}/addresses`,
    { addresses },
    { headers: ifMatch(version) },
  );
  return data;
}
