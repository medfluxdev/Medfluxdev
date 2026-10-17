import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import ResponsibilityChips, { deviceTypesLabel } from "@/components/contracts/detail/ContractHeaderChips";
import type { ContractAssignment } from "@/lib/contract-detail-types";

const FULL: ContractAssignment = {
  contract_type: "Wartungsvertrag", contract_category: null, hospital: "Nordwest Krankenhaus", responsible_department: "Medizintechnik",
  beneficiary_departments: ["Röntgen Diagnostik"], other_departments: [], cost_center: { code: "950000", name: "Radiologie" },
  device_types: ["CT", "MRT", "Angiographie"], responsible: "Developer", further_responsible: [],
} as ContractAssignment;

/** Reihenfolge der Chips einer Zeile als Liste ihrer Texte (ohne Zeilenbeschriftung). */
function sequence(): string[] {
  const row = screen.getByRole("group", { name: "Zuständigkeit" });
  return [...row.querySelectorAll(".tag-chip:not(.chip-row-more)")].map((chip) => chip.textContent!.replace(/\s+/g, " ").trim());
}

describe("Kopf: Zeile „Zuständig“", () => {
  it("feste Reihenfolge: Krankenhaus → Abteilungen → Kostenstelle → Gerätearten → Person; kein „Ändern“ in der Zeile", async () => {
    const { container } = render(<ResponsibilityChips assignment={FULL} canEdit hospitalCount={2} onOpen={() => undefined} />);
    expect(screen.queryByText("Zuständig")).not.toBeInTheDocument();
    expect(sequence()).toEqual([
      "Krankenhaus: Nordwest Krankenhaus",
      "Verantwortliche Abteilung: Medizintechnik",
      "Nutzende Abteilung: Röntgen Diagnostik",
      "Kostenstelle: 950000 Radiologie",
      "Gerätearten: CT · MRT +1",
      "DHauptverantwortlich: Developer",
    ]);
    expect(screen.getByText("Developer").closest(".tag-chip")).toHaveAttribute("title", "Hauptverantwortlich – in der Organisationszuordnung ansehen oder ändern");
    expect(screen.getByText("CT · MRT +1").closest(".tag-chip")).toHaveAttribute("title", "CT · MRT · Angiographie – in der Organisationszuordnung ansehen oder ändern");
    const row = screen.getByRole("group", { name: "Zuständigkeit" });
    expect(within(row).queryByRole("button", { name: /Ändern|Bearbeiten/ })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("bleibt bei fehlenden Angaben in derselben Reihenfolge: Pflichtangaben gestrichelt an ihrem Platz, Rest ohne Lücke", () => {
    render(<ResponsibilityChips assignment={{ ...FULL, responsible: null, responsible_department: null, cost_center: null, device_types: [], beneficiary_departments: [] }} canEdit hospitalCount={2} onOpen={() => undefined} />);
    expect(sequence()).toEqual([
      "Krankenhaus: Nordwest Krankenhaus",
      "Verantwortliche Abteilung – festlegen",
      "Kostenstelle – festlegen",
      "Hauptverantwortlich – festlegen",
    ]);
    expect(screen.getByRole("button", { name: "Hauptverantwortlich – festlegen" })).toHaveClass("tag-chip--missing");
  });

  it("Krankenhaus nur bei mehreren Krankenhäusern; unbekannte Anzahl zeigt es", () => {
    const { rerender } = render(<ResponsibilityChips assignment={FULL} canEdit hospitalCount={1} onOpen={() => undefined} />);
    expect(screen.queryByText("Nordwest Krankenhaus")).not.toBeInTheDocument();
    rerender(<ResponsibilityChips assignment={FULL} canEdit hospitalCount={null} onOpen={() => undefined} />);
    expect(screen.getByText("Nordwest Krankenhaus")).toBeInTheDocument();
  });

  it("ab dem vierten Chip „+N“ (für schmale Bildschirme); Klick zeigt alle", async () => {
    const user = userEvent.setup();
    const { container } = render(<ResponsibilityChips assignment={FULL} canEdit hospitalCount={2} onOpen={() => undefined} />);
    // Krankenhaus + zwei Abteilungen sichtbar; Kostenstelle, Gerätearten, Person dahinter.
    expect(container.querySelectorAll(".chip-slot--extra")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "3 weitere Angaben zeigen" }));
    expect(screen.getByRole("group", { name: "Zuständigkeit" })).toHaveAttribute("data-expanded");
    expect(screen.queryByRole("button", { name: /weitere Angaben/ })).not.toBeInTheDocument();
  });

  it("gestrichelte Pflichtchips führen zur Organisationszuordnung – auch für Lesende", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const { unmount } = render(<ResponsibilityChips assignment={{ ...FULL, responsible: null }} canEdit hospitalCount={2} onOpen={onOpen} />);
    await user.click(screen.getByRole("button", { name: "Hauptverantwortlich – festlegen" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    unmount();
    render(<ResponsibilityChips assignment={{ ...FULL, responsible: null }} canEdit={false} hospitalCount={2} onOpen={onOpen} />);
    const row = screen.getByRole("group", { name: "Zuständigkeit" });
    expect(within(row).getByRole("button", { name: "Hauptverantwortlich – nicht festgelegt" })).toHaveClass("tag-chip--missing");
    expect(within(row).queryByRole("button", { name: /festlegen/ })).not.toBeInTheDocument();
  });

  it("jeder Chip führt zur Quelle (Organisationszuordnung) – auch für Lesende", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<ResponsibilityChips assignment={FULL} canEdit={false} hospitalCount={2} onOpen={onOpen} />);
    const row = screen.getByRole("group", { name: "Zuständigkeit" });
    const chips = [...row.querySelectorAll<HTMLElement>(".tag-chip:not(.chip-row-more)")];
    expect(chips).toHaveLength(6);
    for (const chip of chips) {
      expect(chip.tagName).toBe("BUTTON");
      expect(chip).toHaveAttribute("title", expect.stringContaining("in der Organisationszuordnung ansehen"));
      await user.click(chip);
    }
    expect(onOpen).toHaveBeenCalledTimes(6);
  });

  it("Gerätearten: bis zu zwei Namen ausgeschrieben, Rest als „+N“", () => {
    expect(deviceTypesLabel(["CT", "MRT"])).toBe("CT · MRT");
    expect(deviceTypesLabel(["CT", "MRT", "Angiographie"])).toBe("CT · MRT +1");
    expect(deviceTypesLabel(["CT", "MRT", "A", "B"])).toBe("CT · MRT +2");
  });
});
