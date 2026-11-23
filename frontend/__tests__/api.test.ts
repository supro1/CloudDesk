import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ACCESS_TOKEN_KEY,
  approveTicketAction,
  escalateTicket,
  getCurrentUser,
  getTicketWorkflow,
  listTickets,
  NetworkError,
  rejectTicketAction,
  requestTicketInformation,
  sendTicketReply,
  startTicketWorkflow,
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

  it("uses the documented ticket workflow and action routes", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => new Response(
      JSON.stringify({}),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    await startTicketWorkflow("ticket-1");
    await getTicketWorkflow("ticket-1");
    await approveTicketAction("approval-1", "Verified");
    await rejectTicketAction("approval-1", "Not safe");
    await sendTicketReply("ticket-1", "Reply text");
    await requestTicketInformation("ticket-1", "Please share more details.");
    await escalateTicket("ticket-1", { team: "billing", reason: "Needs review." });

    const requests = fetchMock.mock.calls.map(([url, init]) => ({
      url,
      method: init?.method ?? "GET",
      body: init?.body,
    }));
    expect(requests.map(({ url, method }) => [url, method])).toEqual([
      ["http://localhost:8000/api/v1/tickets/ticket-1/run", "POST"],
      ["http://localhost:8000/api/v1/tickets/ticket-1/workflow", "GET"],
      ["http://localhost:8000/api/v1/approvals/approval-1/approve", "POST"],
      ["http://localhost:8000/api/v1/approvals/approval-1/reject", "POST"],
      ["http://localhost:8000/api/v1/tickets/ticket-1/reply", "POST"],
      ["http://localhost:8000/api/v1/tickets/ticket-1/request-info", "POST"],
      ["http://localhost:8000/api/v1/tickets/ticket-1/escalate", "POST"],
    ]);
    expect(JSON.parse(String(requests[2].body))).toEqual({ reason: "Verified" });
    expect(JSON.parse(String(requests[4].body))).toEqual({ body: "Reply text" });
    expect(JSON.parse(String(requests[6].body))).toEqual({ team: "billing", reason: "Needs review." });
  });
});
