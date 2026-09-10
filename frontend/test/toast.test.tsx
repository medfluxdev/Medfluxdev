import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, TOAST_DURATION_MS, useToast } from "@/components/ui/Toast";

function Probe() {
  const toast = useToast();
  return (
    <button
      type="button"
      onClick={() => toast("Vertrag archiviert.", "success")}
    >
      Auslösen
    </button>
  );
}

describe("Toast-System (UAT Defect E)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("zeigt Meldungen unten rechts (aria-live polite, role=status)", () => {
    render(
      <ToastProvider>
        <Probe />
      </ToastProvider>
    );
    fireEvent.click(screen.getByRole("button", { name: "Auslösen" }));
    expect(screen.getByRole("status")).toHaveTextContent("Vertrag archiviert.");
    const viewport = screen.getByLabelText("Benachrichtigungen");
    expect(viewport).toHaveAttribute("aria-live", "polite");
    expect(viewport.className).toContain("toast-viewport");
  });

  it("verblasst nach ~5s automatisch", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Probe />
      </ToastProvider>
    );
    fireEvent.click(screen.getByRole("button", { name: "Auslösen" }));
    expect(screen.getByRole("status")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(TOAST_DURATION_MS + 10);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("meldet Fehler als alert (nicht nur optisch)", () => {
    function ErrorProbe() {
      const toast = useToast();
      return (
        <button type="button" onClick={() => toast("Nicht gespeichert.", "error")}>
          Fehler
        </button>
      );
    }
    render(
      <ToastProvider>
        <ErrorProbe />
      </ToastProvider>
    );
    fireEvent.click(screen.getByRole("button", { name: "Fehler" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Nicht gespeichert.");
  });
});