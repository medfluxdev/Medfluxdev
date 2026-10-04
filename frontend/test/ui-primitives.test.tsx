import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import Dialog from "@/components/ui/Dialog";
import DataTable from "@/components/ui/DataTable";
import Drawer from "@/components/ui/Drawer";
import Tabs from "@/components/ui/Tabs";
import Breadcrumbs from "@/components/ui/Breadcrumbs";
import EmptyState from "@/components/ui/EmptyState";

function TabsHarness() {
  const [active, setActive] = useState<"a" | "b" | "c">("a");
  return <Tabs label="Bereiche" active={active} onChange={setActive} items={[{ key: "a", label: "Übersicht" }, { key: "b", label: "Stammdaten" }, { key: "c", label: "Finanzen" }]} />;
}

describe("UI-Bausteine", () => {
  it("Reiter: Pfeiltasten, Pos1/Ende und nur der aktive Reiter ist fokussierbar", async () => {
    const user = userEvent.setup();
    render(<TabsHarness />);
    const first = screen.getByRole("tab", { name: "Übersicht" });
    expect(first).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Finanzen" })).toHaveAttribute("tabindex", "-1");
    first.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Stammdaten" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Stammdaten" })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Finanzen" })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Übersicht" })).toHaveAttribute("aria-selected", "true");
  });

  it("Dialog: Fokus im Dialog, Escape schließt, barrierefrei", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(<Dialog open title="Vertrag löschen?" description="Das kann rückgängig gemacht werden." onClose={onClose} actions={<><button type="button">Abbrechen</button><button type="button">Löschen</button></>} />);
    const dialog = screen.getByRole("dialog", { name: "Vertrag löschen?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(within(dialog).getByRole("button", { name: "Abbrechen" })).toHaveFocus();
    await user.tab();
    await user.tab();
    expect(within(dialog).getByRole("button", { name: "Abbrechen" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Seitenleiste: Schließen-Schaltfläche und Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Drawer open title="Vorschau" onClose={onClose}><p>Inhalt</p></Drawer>);
    await user.click(screen.getByRole("button", { name: "Schließen" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Tabelle: sortiert per Kopfzeile und meldet den Zustand über aria-sort", async () => {
    const user = userEvent.setup();
    const rows = [{ id: "1", name: "Reinigung", cost: 14400 }, { id: "2", name: "Wartung", cost: 42000 }, { id: "3", name: "Software", cost: 18000 }];
    render(<DataTable caption="Verträge" rowKey={(row) => row.id} rows={rows} columns={[
      { key: "name", label: "Vertrag", render: (row) => row.name, rowHeader: true, sortValue: (row) => row.name },
      { key: "cost", label: "Kosten", render: (row) => row.cost, numeric: true, sortValue: (row) => row.cost },
    ]} />);
    await user.click(screen.getByRole("button", { name: "Kosten" }));
    expect(screen.getByRole("columnheader", { name: /Kosten/ })).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["Reinigung", "Software", "Wartung"]);
    await user.click(screen.getByRole("button", { name: /Kosten/ }));
    expect(screen.getAllByRole("rowheader")[0]).toHaveTextContent("Wartung");
  });

  it("Brotkrumen und leerer Zustand", () => {
    render(<><Breadcrumbs items={[{ label: "Verträge", href: "/register" }, { label: "000001" }]} /><EmptyState title="Keine Verträge" action={<button type="button">Vertrag anlegen</button>}>Legen Sie den ersten Vertrag an.</EmptyState></>);
    expect(screen.getByRole("link", { name: "Verträge" })).toHaveAttribute("href", "/register");
    expect(screen.getByText("000001")).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "Keine Verträge" })).toBeInTheDocument();
  });
});
