import axios, { AxiosError } from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Registered by the store (avoids an api <-> store import cycle). Logs the user out in-app
// instead of a hard page reload, so state is reset and error messages are not lost.
let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (handler: () => void) => {
  onUnauthorized = handler;
};

const AUTH_ENDPOINTS = ['/auth/login/', '/auth/refresh/'];

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const url = error.config?.url ?? '';
    // A 401 from the login call means "wrong credentials", not "session expired".
    if (error.response?.status === 401 && !AUTH_ENDPOINTS.some((e) => url.includes(e))) {
      onUnauthorized?.();
    }
    return Promise.reject(error);
  }
);

interface ApiErrorBody {
  error?: unknown;
  detail?: unknown;
}

const flatten = (value: unknown): string => {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(flatten).filter(Boolean).join(' ');
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([field, v]) => (field === 'non_field_errors' || field === 'detail' ? flatten(v) : `${field}: ${flatten(v)}`))
      .join('; ');
  }
  return String(value);
};

/** One human-readable message from any API error shape. */
export const apiErrorMessage = (err: unknown, fallback: string): string => {
  if (axios.isAxiosError<ApiErrorBody>(err)) {
    const body = err.response?.data;
    const msg = flatten(body?.error) || flatten(body?.detail);
    if (msg) return msg;
    if (!err.response) return 'Network error: the server could not be reached.';
  }
  return fallback;
};

export const apiErrorStatus = (err: unknown): number | undefined =>
  axios.isAxiosError(err) ? err.response?.status : undefined;

/** Short-lived handshake ticket so the JWT never appears in a WebSocket URL. */
export const fetchWsTicket = async (): Promise<string> => {
  const res = await apiClient.post<{ ticket: string; expires_in: number }>('/auth/ws-ticket/');
  return res.data.ticket;
};
