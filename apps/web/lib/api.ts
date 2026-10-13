/** Thin API client for server components and client data fetching.

 * Milestone 1 pages render labeled fixtures. This client is the contract point for
 * Milestone 3+, when a typed client is generated from the FastAPI OpenAPI schema.
 * It is intentionally dependency-free (uses global fetch + JSON).
 */

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...init,
  });

  if (!res.ok) {
    let payload: { error?: { code?: string; message?: string } } = {};
    try {
      payload = (await res.json()) as typeof payload;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(
      res.status,
      payload.error?.code ?? "http_error",
      payload.error?.message ?? `Request failed with status ${res.status}`,
    );
  }

  return (await res.json()) as T;
}