const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  if (typeof window !== "undefined") {
    const token = window.sessionStorage.getItem("jobflow_token");
    if (token) result.set("Authorization", `Bearer ${token}`);
  }
  return result;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, init);
  await ensureSuccess(response);
  return response.json() as Promise<T>;
}

async function ensureSuccess(response: Response): Promise<void> {
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Please sign in to continue.");
    }
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = authHeaders(init?.headers);
  if (init?.body !== undefined) headers.set("Content-Type", "application/json");
  return request<T>(path, {
    ...init,
    headers,
  });
}

export async function apiForm<T>(path: string, formData: FormData, init?: RequestInit): Promise<T> {
  return request<T>(path, {
    ...init,
    method: init?.method ?? "POST",
    body: formData,
    headers: authHeaders(init?.headers),
  });
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    headers: authHeaders(),
  });
  await ensureSuccess(response);
  return response.blob();
}

export type TokenResponse = { access_token: string; token_type: "bearer" };
