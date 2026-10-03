import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost, apiUpload, ApiError, userMessageForStatus } from "@/lib/api";

// Interaktions-Audit: Ladezustände müssen IMMER terminieren. Der API-Layer
// bekommt pro Request ein Standard-Timeout; haengt der Server, endet der
// Zustand mit einem ehrlichen Fehler statt endlosem "wird geladen…".

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
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
  it("bricht einen haengenden GET nach dem Standard-Timeout mit verständlichem Fehler ab", async () => {
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
    p.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(21000);
    await expect(p).rejects.toThrow("Die Anfrage hat zu lange gedauert");
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
    await expect(p).rejects.toThrow("Die Anfrage hat zu lange gedauert");
  });

  it("gibt lokalen KI-Uploads ein eigenes 30min-Fenster statt des normalen 20s-Timeouts", async () => {
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
    const file = new File(["x"], "vertrag.pdf", { type: "application/pdf" });
    const p = apiUpload<unknown>("/api/documents/import", [file], "test-org");
    p.catch(() => undefined);
    await vi.advanceTimersByTimeAsync(21000);
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    await vi.advanceTimersByTimeAsync(1_780_000);
    await expect(p).rejects.toThrow("Die Anfrage hat zu lange gedauert");
  });

  it("liefert für HTTP-Fehler standardisierte deutsche Meldungen und den Status", async () => {
    stubFetch(async () => new Response("kaputt", { status: 500 }));
    try {
      await apiGet<unknown>("/api/500");
      throw new Error("Erwarteter Fehler wurde nicht ausgelöst");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(500);
      expect((error as Error).message).toBe("Der Server ist momentan nicht verfügbar. Bitte versuchen Sie es erneut.");
    }
  });

  it("unterscheidet 401, 403 und 404 verständlich", () => {
    expect(userMessageForStatus(401)).toMatch(/Sitzung ist abgelaufen/);
    expect(userMessageForStatus(403)).toMatch(/keine Berechtigung/);
    expect(userMessageForStatus(404)).toMatch(/nicht gefunden/);
  });

  it("signalisiert eine abgelaufene Sitzung bei geschützten Requests", async () => {
    const onExpired = vi.fn();
    window.addEventListener("medflux:session-expired", onExpired);
    stubFetch(async () => new Response("", { status: 401 }));

    await expect(apiGet<unknown>("/api/contracts")).rejects.toThrow(/Sitzung ist abgelaufen/);
    expect(onExpired).toHaveBeenCalledTimes(1);

    window.removeEventListener("medflux:session-expired", onExpired);
  });

  it("behandelt falsche Login-Daten als 401 ohne Session-Redirect-Signal", async () => {
    const onExpired = vi.fn();
    window.addEventListener("medflux:session-expired", onExpired);
    stubFetch(async () => new Response("", { status: 401 }));

    await expect(apiPost<unknown>("/api/auth/login", { email: "test@example.org", password: "falsch" })).rejects.toThrow(/Sitzung ist abgelaufen/);
    expect(onExpired).not.toHaveBeenCalled();

    window.removeEventListener("medflux:session-expired", onExpired);
  });
});
