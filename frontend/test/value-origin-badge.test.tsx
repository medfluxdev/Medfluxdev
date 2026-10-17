import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AiOrigin, { AiReviewContext } from "@/components/ui/AiOrigin";
import ValueOriginBadge from "@/components/contracts/detail/ValueOriginBadge";

describe("Vertragswerte – Herkunft", () => {
  it.each([
    ["extracted", "KI · Ungeprüft"],
    ["reviewed", "KI · Bestätigt"],
    ["corrected", "korrigiert"],
    ["calculated", "berechnet"],
    ["missing", "Fehlt"],
    ["system", "gepflegt"],
  ] as const)("zeigt %s als %s", (kind, label) => {
    render(<ValueOriginBadge kind={kind} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe("KI-Plakette – Sprung zur Prüfung", () => {
  it("führt auf der Vertragsseite zur Prüfung der Angabe, sonst zur Fundstelle; ohne beides kein Knopf", () => {
    const openSource = vi.fn();
    const openReview = vi.fn();
    const { rerender } = render(<AiReviewContext.Provider value={openReview}><AiOrigin state="confirmed" subject="Pauschale" factKey="costs.annual" onOpenSource={openSource} /></AiReviewContext.Provider>);
    fireEvent.click(screen.getByRole("button", { name: "KI · Bestätigt (Pauschale) – Prüfung öffnen" }));
    expect(openReview).toHaveBeenCalledWith({ factKeys: ["costs.annual"], subject: "Pauschale", openSource });
    expect(openSource).not.toHaveBeenCalled();
    rerender(<AiOrigin state="unreviewed" subject="Pauschale" onOpenSource={openSource} />);
    fireEvent.click(screen.getByRole("button", { name: "KI · Ungeprüft (Pauschale) – Quelle öffnen" }));
    expect(openSource).toHaveBeenCalledOnce();
    rerender(<AiOrigin state="unreviewed" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
