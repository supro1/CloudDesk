import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ACCESS_TOKEN_KEY,
  getCurrentUser,
  listTickets,
  NetworkError,
  USER_KEY,
} from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("typed API client", () => {
  it("adds the bearer token and serializes list pagination", async () => {
    window.localStorage.setItem("clouddesk.access_token", "signed-token");
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(
      JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    await listTickets({ limit: 20, offset: 40 });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/tickets?limit=20&offset=40");
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer signed-token");
    expect(new Headers(options.headers).get("Accept")).toBe("application/json");
  });

  it("exposes API detail and request IDs for failed responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Not authorized" }),
      { status: 403, headers: { "X-Request-ID": "req-123" } },
    )));

    await expect(getCurrentUser("token")).rejects.toMatchObject({
      message: "Not authorized",
      status: 403,
      requestId: "req-123",
    });
  });

  it("clears a rejected session before returning an unauthorized error", async () => {
    window.history.replaceState({}, "", "/login");
    window.localStorage.setItem(ACCESS_TOKEN_KEY, "expired-token");
    window.localStorage.setItem(USER_KEY, JSON.stringify({ email: "agent@example.test" }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Invalid or expired token" }),
      { status: 401 },
    )));

    await expect(getCurrentUser()).rejects.toMatchObject({ status: 401 });
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(window.localStorage.getItem(USER_KEY)).toBeNull();
  });

  it("reports network failures as retryable network errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(listTickets()).rejects.toBeInstanceOf(NetworkError);
  });
});
