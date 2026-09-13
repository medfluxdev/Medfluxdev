import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiUpload } from "@/lib/api";

// Interaktions-Audit: Ladezustände müssen IMMER terminieren. Der API-Layer
// bekommt pro Request ein Standard-Timeout; haengt der Server, endet der
// Zustand mit einem ehrlichen Fehler statt endlosem "wird geladen…".

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();

  it("bricht auch haengende Uploads ueber ihren Timeout ab", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit): Promise<Response> =>
          new Promise<Response>((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError"))
            );
          })
      )
    );
    vi.useFakeTimers();
    const file = new File(["x"], "contract.pdf", { type: "application/pdf" });
    const p = apiUpload<unknown>("/api/documents/import", [file], "hospital", 500);
    p.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(600);
    await expect(p).rejects.toThrow();
  });

});

function stubFetch(promiseFor: (init: RequestInit) => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      (_url: string, init: RequestInit): Promise<Response> =>
        promiseFor(init)
    )
  );
}

describe("API-Schicht: garantierte Terminierung", () => {
  it("bricht einen haengenden GET nach dem Standard-Timeout mit Fehler ab", async () => {
    // Ein fetch, das NIE aufloest, aber auf das AbortSignal hoert (Timeout).
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit): Promise<Response> =>
          new Promise<Response>((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError"))
            );
          })
      )
    );

    vi.useFakeTimers();
    const p = apiGet<unknown>("/api/never");
    p.catch(() => undefined); // Rejection wird hier bewusst behandelt.
    await vi.advanceTimersByTimeAsync(21000);
    await expect(p).rejects.toThrow();
  });

  it("loest ueber den Timeout hinausgehende 200-Responses korrekt auf", async () => {
    stubFetch(async () => {
      const body = JSON.stringify({ ok: true });
      return new Response(body, { status: 200 });
    });
    const res = await apiGet<{ ok: boolean }>("/api/ok");
    expect(res).toEqual({ ok: true });
  });

  it("respektiert einen expliziten Timeout-Parameter", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit): Promise<Response> =>
          new Promise<Response>((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError"))
            );
          })
      )
    );
    vi.useFakeTimers();
    const p = apiGet<unknown>("/api/slow", undefined, 500);
    p.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(600);
    await expect(p).rejects.toThrow();
  });

  it("meldet HTTP-Fehler weiterhin als ehrlichen Fehler", async () => {
    stubFetch(async () => new Response("kaputt", { status: 500 }));
    await expect(apiGet<unknown>("/api/500")).rejects.toThrow("Request failed: 500");
  });
});