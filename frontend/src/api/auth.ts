import { apiFetch, clearToken, setToken } from './client';

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  is_admin: boolean;
  is_active: boolean;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = LoginPayload & {
  full_name?: string;
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
