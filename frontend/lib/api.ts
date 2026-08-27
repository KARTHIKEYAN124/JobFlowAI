const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === "production" ? "/backend" : "http://localhost:8000");
const TOKEN_KEY = "jobflow_token";

export function clearSession(): void {
  if (typeof window !== "undefined") window.sessionStorage.removeItem(TOKEN_KEY);
}

export function storeSession(token: string): void {
  if (typeof window !== "undefined") window.sessionStorage.setItem(TOKEN_KEY, token);
}

export function hasUsableSession(): boolean {
  if (typeof window === "undefined") return false;
  const token = window.sessionStorage.getItem(TOKEN_KEY);
  if (!token) return false;
  try {
    const encoded = token.split(".")[1];
    const padded = encoded.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(encoded.length / 4) * 4, "=");
    const payload = JSON.parse(window.atob(padded)) as { exp?: number };
    if (typeof payload.exp !== "number" || payload.exp * 1000 <= Date.now()) {
      clearSession();
      return false;
    }
    return true;
  } catch {
    clearSession();
    return false;
  }
}

function authHeaders(headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  if (typeof window !== "undefined") {
    const token = hasUsableSession() ? window.sessionStorage.getItem(TOKEN_KEY) : null;
    if (token) result.set("Authorization", `Bearer ${token}`);
  }
  return result;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, init);
  await ensureSuccess(response, path);
  return response.json() as Promise<T>;
}

async function ensureSuccess(response: Response, path: string): Promise<void> {
  if (!response.ok) {
    if (response.status === 401) {
      if (path.startsWith("/auth/")) throw new Error("Invalid email or password.");
      clearSession();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/auth/")) {
        window.location.replace("/auth/sign-in?reason=session-expired");
      }
      throw new Error("Your session expired. Please sign in again.");
    }
    const body = await response.json().catch(() => ({ detail: "Request failed" })) as { detail?: unknown };
    const detail = Array.isArray(body.detail)
      ? body.detail.map(item => typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)).join(" ")
      : typeof body.detail === "string" ? body.detail : null;
    throw new Error(detail ?? `Request failed (${response.status})`);
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
  await ensureSuccess(response, path);
  return response.blob();
}

export type TokenResponse = { access_token: string; token_type: "bearer" };
