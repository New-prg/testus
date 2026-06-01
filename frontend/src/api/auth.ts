import { apiFetch, clearToken, setToken } from './client';

export type User = {
  id: string;
  login: string;
  full_name: string | null;
  role: string;
  is_admin: boolean;
  is_active: boolean;
  pilot_server_address: string | null;
  pilot_node: number | null;
  is_demo: boolean;
  sync_started_at: string | null;
  last_sync_completed_at: string | null;
  next_sync_at: string | null;
  last_sync_error: string | null;
};

export type LoginPayload = {
  login: string;
  password: string;
};

export type RegisterPayload = LoginPayload & {
  full_name?: string;
  server_address: string;
  node: number;
};

type TokenResponse = {
  access_token: string;
  token_type: string;
};

export async function login(payload: LoginPayload): Promise<User> {
  const token = await apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: payload,
  });
  setToken(token.access_token);
  return me();
}

export async function register(payload: RegisterPayload): Promise<User> {
  return apiFetch<User>('/auth/register', {
    method: 'POST',
    body: payload,
  });
}

export async function me(): Promise<User> {
  return apiFetch<User>('/auth/me');
}

export function logout(): void {
  clearToken();
}
