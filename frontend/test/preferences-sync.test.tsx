import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readPreferences, useServerPreferenceSync, writePreferences, DEFAULT_PREFERENCES } from "@/components/shell/preferences";

const api = vi.hoisted(() => ({ apiGet: vi.fn(), apiPut: vi.fn().mockResolvedValue({}) }));
vi.mock("@/lib/api", () => api);

afterEach(() => {
  vi.useRealTimers();
  localStorage.clear();
  api.apiGet.mockReset();
  api.apiPut.mockClear();
  document.documentElement.removeAttribute("data-theme");
});

describe("Darstellung auf dem Server", () => {
  it("übernimmt beim Anmelden die Serverkopie ohne sie zurückzuschreiben", async () => {
    api.apiGet.mockResolvedValue({ preferences: { theme: "dark", text_size: "xlarge", density: "compact", sidebar_collapsed: false, developer_mode: false } });
    renderHook(() => useServerPreferenceSync("u-1"));
    await waitFor(() => expect(document.documentElement).toHaveAttribute("data-theme", "dark"));
    expect(readPreferences()).toMatchObject({ theme: "dark", textSize: "xlarge", density: "compact" });
    expect(api.apiPut).not.toHaveBeenCalled();
  });

  it("legt die lokale Einstellung an, wenn der Server noch keine hat, und speichert Änderungen gebündelt", async () => {
    api.apiGet.mockResolvedValue({ preferences: null });
    writePreferences({ ...DEFAULT_PREFERENCES, textSize: "large" });
    renderHook(() => useServerPreferenceSync("u-1"));
    await waitFor(() => expect(api.apiPut).toHaveBeenCalledWith("/api/profile/preferences", expect.objectContaining({ text_size: "large" })));
    api.apiPut.mockClear();
    vi.useFakeTimers();
    act(() => {
      writePreferences({ ...readPreferences(), theme: "light" });
      writePreferences({ ...readPreferences(), theme: "dark" });
    });
    act(() => { vi.advanceTimersByTime(700); });
    expect(api.apiPut).toHaveBeenCalledTimes(1);
    expect(api.apiPut).toHaveBeenCalledWith("/api/profile/preferences", expect.objectContaining({ theme: "dark", text_size: "large" }));
  });

  it("synchronisiert ohne Anmeldung nicht", () => {
    renderHook(() => useServerPreferenceSync(null));
    expect(api.apiGet).not.toHaveBeenCalled();
  });
});
