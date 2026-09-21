const BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const where = Array.isArray(d?.loc) ? d.loc.slice(1).join(".") : "";
        return where ? `${where}: ${d?.msg}` : String(d?.msg ?? "Invalid input");
      })
      .join("; ");
  }
  return "Something went wrong";
}

export async function api<T = unknown>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const hasBody = options.body !== undefined;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: options.method ?? "GET",
      headers: hasBody ? { "Content-Type": "application/json" } : undefined,
      body: hasBody ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(`Cannot reach the backend at ${BASE}. Is it running?`, 0);
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(detailText((data as { detail?: unknown } | null)?.detail), res.status);
  }
  return data as T;
}