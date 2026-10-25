import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import FieldSuggestion from "@/components/contracts/detail/FieldSuggestion";

describe("FieldSuggestion", () => {
  it("bestätigter Wert: Quelle, Seite und Übernehmen – ohne Beibehalten/Anders", async () => {
    const onApply = vi.fn();
    render(<FieldSuggestion kind="confirmed" value="Wartungsvertrag" page={1} onApply={onApply} onKeep={() => {}} onOther={() => {}} />);
    expect(screen.getByText("Wartungsvertrag")).toBeInTheDocument();
    expect(screen.getByText(/In der Prüfung bestätigt · Seite 1/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Beibehalten" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Übernehmen" }));
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("KI-Vorschlag: Übernehmen und Anders", async () => {
    const onOther = vi.fn();
    render(<FieldSuggestion kind="ai" value="Service Vertrag" page={2} onApply={() => {}} onOther={onOther} />);
    expect(screen.getByText(/KI-Vorschlag, noch nicht geprüft · Seite 2/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Anders" }));
    expect(onOther).toHaveBeenCalledTimes(1);
  });

  it("Widerspruch: „Die Prüfung sagt …“ mit Übernehmen und Beibehalten", async () => {
    const onKeep = vi.fn();
    const { container } = render(<FieldSuggestion kind="conflict" value="Full-Service-Vertrag" onApply={() => {}} onKeep={onKeep} />);
    expect(screen.getByText(/Die Prüfung sagt/)).toBeInTheDocument();
    expect(screen.getByText("Full-Service-Vertrag")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Beibehalten" }));
    expect(onKeep).toHaveBeenCalledTimes(1);
    expect(await axe(container)).toHaveNoViolations();
  });
});
