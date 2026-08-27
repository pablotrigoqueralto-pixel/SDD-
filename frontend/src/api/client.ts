import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

import type { components } from '@/api/schema';
import { env } from '@/lib/env';
import { toProblem } from '@/lib/problem';
import { sessionStore } from '@/store/session.store';

type TokenResponse = components['schemas']['TokenResponse'];

export const API_PREFIX = '/api/v1';

/** Single Axios instance: base URL, cookies for the refresh token, bearer token, problem mapping. */
export const apiClient = axios.create({
  baseURL: `${env.VITE_API_URL}${API_PREFIX}`,
  withCredentials: true,
  timeout: 15_000,
  headers: { Accept: 'application/json' },
});

/** Header for optimistic-locking updates. */
export function ifMatch(version: number): Record<string, string> {
  return { 'If-Match': `"${version}"` };
}

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

let refreshInFlight: Promise<string | null> | null = null;

function isAuthEndpoint(url: string | undefined): boolean {
  return Boolean(url && (url.includes('/auth/login') || url.includes('/auth/refresh')));
}

/** Refresh once for all concurrent 401s; resolves to the new access token or null. */
export async function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= (async () => {
    try {
      const response = await axios.post<TokenResponse>(
        `${env.VITE_API_URL}${API_PREFIX}/auth/refresh`,
        null,
        { withCredentials: true, timeout: 15_000 },
      );
      sessionStore.getState().setSession(response.data.access_token, response.data.user);
      return response.data.access_token;
    } catch {
      sessionStore.getState().clear();
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

apiClient.interceptors.request.use((config) => {
  const token = sessionStore.getState().accessToken;
  if (token && !isAuthEndpoint(config.url)) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const status = error.response?.status;
    if (status === 401 && config && !config._retried && !isAuthEndpoint(config.url)) {
      config._retried = true;
      const token = await refreshAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
        return apiClient.request(config);
      }
    }
    throw toProblem(error);
  },
);
