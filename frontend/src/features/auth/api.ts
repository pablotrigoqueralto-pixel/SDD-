import { apiClient, ifMatch } from '@/api/client';
import type { components } from '@/api/schema';

export type TokenResponse = components['schemas']['TokenResponse'];
export type MeRead = components['schemas']['MeRead'];
export type LoginRequest = components['schemas']['LoginRequest'];
export type PasswordChangeRequest = components['schemas']['PasswordChangeRequest'];

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', payload);
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function getMe(): Promise<MeRead> {
  const { data } = await apiClient.get<MeRead>('/me');
  return data;
}

export async function renameMe(fullName: string, version: number): Promise<MeRead> {
  const { data } = await apiClient.patch<MeRead>(
    '/me',
    { full_name: fullName },
    { headers: ifMatch(version) },
  );
  return data;
}

export async function changePassword(payload: PasswordChangeRequest): Promise<void> {
  await apiClient.post('/auth/password', payload);
}
