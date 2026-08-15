export function gatewayFetch(path: string, init: RequestInit = {}, requestId?: string | null) {
  const base = process.env.GATEWAY_URL || "http://localhost:8000";
  const timeout = Number(process.env.GATEWAY_TIMEOUT_MS || 5000);
  const headers = new Headers(init.headers);
  headers.set("x-request-id", requestId || crypto.randomUUID());
  return fetch(new URL(path, base), {
    ...init,
    headers,
    cache: "no-store",
    signal: init.signal || AbortSignal.timeout(timeout),
  });
}
