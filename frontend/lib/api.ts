import type {
  AuthenticatedProfile,
  Customer,
  CustomerFilters,
  Escalation,
  EscalationFilters,
  KnowledgeArticle,
  LoginResponse,
  Page,
  Pagination,
  Ticket,
  TicketFilters,
} from "@/lib/types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const API_PREFIX = "/api/v1";
export const ACCESS_TOKEN_KEY = "clouddesk.access_token";
export const USER_KEY = "clouddesk.user";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(message = "The support API could not be reached. Check the connection and try again.") {
    super(message);
    this.name = "NetworkError";
  }
}

type RequestOptions = RequestInit & {
  token?: string | null;
  redirectOnUnauthorized?: boolean;
};

function storedToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token = storedToken(), redirectOnUnauthorized = true, ...init } = options;
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, { ...init, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new NetworkError();
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body: unknown = await response.json();
      if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the status-based message when the server does not return JSON.
    }
    const error = new ApiError(message, response.status, response.headers.get("X-Request-ID") ?? undefined);
    if (response.status === 401 && redirectOnUnauthorized && typeof window !== "undefined") {
      window.localStorage.removeItem(ACCESS_TOKEN_KEY);
      window.localStorage.removeItem(USER_KEY);
      if (window.location.pathname !== "/login") {
        window.location.assign("/login?reason=expired");
      }
    }
    throw error;
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function queryString(params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export function login(email: string): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email }),
    token: null,
    redirectOnUnauthorized: false,
  });
}

export function getCurrentUser(token?: string | null): Promise<AuthenticatedProfile> {
  return request<AuthenticatedProfile>("/auth/me", { token });
}

export function listTickets(
  params: Pagination & TicketFilters = {},
): Promise<Page<Ticket>> {
  return request<Page<Ticket>>(`/tickets${queryString(params)}`);
}

export function listCustomers(
  params: Pagination & CustomerFilters = {},
): Promise<Page<Customer>> {
  return request<Page<Customer>>(`/customers${queryString(params)}`);
}

export function listKnowledge(params: Pagination = {}): Promise<Page<KnowledgeArticle>> {
  return request<Page<KnowledgeArticle>>(`/knowledge${queryString(params)}`);
}

export function listEscalations(
  params: Pagination & EscalationFilters = {},
): Promise<Page<Escalation>> {
  return request<Page<Escalation>>(`/escalations${queryString(params)}`);
}
