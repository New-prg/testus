const TOKEN_KEY = 'driving-efficiency-token';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export type ApiRequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function buildHeaders(options?: ApiRequestOptions): Headers {
  const headers = new Headers(options?.headers);
  const token = getToken();

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (options?.body !== undefined && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return headers;
}

function normalizePath(path: string): string {
  const prefixedPath = path.startsWith('/api') ? path : `/api${path.startsWith('/') ? path : `/${path}`}`;
  return `${apiBaseUrl}${prefixedPath}`;
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export async function apiFetch<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const response = await fetch(normalizePath(path), {
    ...options,
    headers: buildHeaders(options),
    body: options.body instanceof FormData ? options.body : options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    const details = await parseResponse(response).catch(() => undefined);
    const message =
      typeof details === 'object' && details && 'detail' in details
        ? String((details as { detail: unknown }).detail)
        : `Запрос завершился с ошибкой ${response.status}`;

    if (response.status === 401) {
      clearToken();
    }

    throw new ApiError(message, response.status, details);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return parseResponse(response) as Promise<T>;
}

export async function apiFetchBlob(path: string, options: ApiRequestOptions = {}): Promise<Blob> {
  const response = await fetch(normalizePath(path), {
    ...options,
    headers: buildHeaders(options),
    body: options.body instanceof FormData ? options.body : options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    const details = await parseResponse(response).catch(() => undefined);
    const message =
      typeof details === 'object' && details && 'detail' in details
        ? String((details as { detail: unknown }).detail)
        : `Запрос завершился с ошибкой ${response.status}`;
    throw new ApiError(message, response.status, details);
  }

  return response.blob();
}
