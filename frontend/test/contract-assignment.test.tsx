import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import ContractAssignmentCard from "@/components/contracts/detail/ContractAssignmentCard";

const FULL = {
  hospital: "Nordwest Krankenhaus", responsible_department: "Medizintechnik", beneficiary_departments: ["Haustechnik"],
  other_departments: [], cost_center: { code: "950000", name: "Radiologie" }, responsible: "Maria Becker", further_responsible: ["Jonas Kurz", "Lea Wolf"],
};

describe("Übersicht: Organisation & Zuständigkeit", () => {
  it("zeigt Krankenhaus, Abteilungen, Kostenstelle und Verantwortliche", async () => {
    const { container } = render(<ContractAssignmentCard contractId="c-1" assignment={FULL} canEdit />);
    expect(screen.getByRole("heading", { name: "Organisation & Zuständigkeit" })).toBeInTheDocument();
    for (const text of ["Nordwest Krankenhaus", "Medizintechnik", "Haustechnik", "950000 · Radiologie", "Maria Becker", "Jonas Kurz, Lea Wolf"]) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Zuordnung ändern" })).toHaveAttribute("href", "/contracts/c-1?tab=register&abschnitt=ownership");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("fehlende Angaben: mit Recht „Festlegen“, sonst „Nicht festgelegt“", () => {
    const empty = { hospital: null, responsible_department: null, beneficiary_departments: [], other_departments: [], cost_center: null, responsible: null, further_responsible: [] };
    const { unmount } = render(<ContractAssignmentCard contractId="c-1" assignment={empty} canEdit />);
    expect(screen.getByText("Organisationsweit")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kostenstelle festlegen" })).toHaveAttribute("href", "/contracts/c-1?tab=register&abschnitt=ownership");
    unmount();
    render(<ContractAssignmentCard contractId="c-1" assignment={empty} canEdit={false} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getAllByText("Nicht festgelegt").length).toBe(3);
  });
});
