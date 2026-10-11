import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import SearchSelect from "@/components/ui/SearchSelect";
import { departmentDefinition, departmentParentOptions, type OrganizationContext } from "@/components/master-data/definitions/organization";

const context: OrganizationContext = {
  hospitals: [{ id: "h-1", name: "Nordwest", code: "NW", is_active: true } as OrganizationContext["hospitals"][number]],
  departments: [
    { id: "k-1", hospital_id: "h-1", parent_id: null, name: "Medizinische Klinik", code: "MK", unit_type: "klinik", is_active: true },
    { id: "a-1", hospital_id: "h-1", parent_id: "k-1", name: "Kardiologie", code: "KAR", unit_type: "abteilung", is_active: true },
    { id: "s-1", hospital_id: "h-1", parent_id: null, name: "Station 3", code: "ST3", unit_type: "station", is_active: true, placement_issue: "Eine Station steht unter einer Klinik oder Abteilung." },
    { id: "x-1", hospital_id: "h-1", parent_id: null, name: "Alte Einheit", code: "ALT", unit_type: null, is_active: true },
  ],
  costCenters: [],
  placementRules: {
    klinik: { parents: [null], text: "Eine Klinik steht direkt unter dem Krankenhaus." },
    abteilung: { parents: [null, "klinik"], text: "Eine Abteilung steht unter einer Klinik oder direkt unter dem Krankenhaus." },
    station: { parents: ["klinik", "abteilung"], text: "Eine Station steht unter einer Klinik oder Abteilung." },
  },
};

describe("Abteilungsstruktur: nur passende übergeordnete Einheiten", () => {
  it("filtert nach Typ; Einheiten ohne Typ bleiben wählbar; ohne Typ alles", () => {
    const names = (type?: string) => departmentParentOptions(context, "h-1", null, type).map((item) => item.label);
    expect(names("abteilung")).toEqual(["Alte Einheit", "Medizinische Klinik"]);
    expect(names("station")).toEqual(["Alte Einheit", "Medizinische Klinik", "Medizinische Klinik › Kardiologie"]);
    expect(names(undefined)).toHaveLength(4);
  });

  it("Klinik: kein übergeordneter Eintrag außer „direkt im Krankenhaus“; Station: Pflicht", () => {
    const parent = (type: string) => departmentDefinition.fields(context, { hospital_id: "h-1", unit_type: type }, null).find((field) => field.key === "parent_id")!;
    expect(parent("klinik").emptyOption).toBe("Keine – direkt im Krankenhaus");
    expect(parent("klinik").options?.map((item) => item.label)).toEqual(["Alte Einheit"]);
    expect(parent("station").emptyOption).toBeUndefined();
    expect(parent("station").hint).toContain("Eine Station steht unter einer Klinik oder Abteilung.");
  });

  it("markiert bestehende Abweichungen in der Liste", () => {
    const column = departmentDefinition.columns(context).find((item) => item.key === "placement")!;
    render(<div>{column.render(context.departments[2], context)}</div>);
    expect(screen.getByText("Prüfen")).toBeInTheDocument();
    expect(screen.getByText(/Eine Station steht unter/)).toBeInTheDocument();
  });
});

function Harness() {
  const [value, setValue] = useState("");
  return <>
    <label htmlFor="parent">Übergeordnete Einheit</label>
    <SearchSelect id="parent" value={value} onChange={setValue} emptyLabel="Keine – direkt im Krankenhaus"
      options={[{ value: "k-1", label: "Medizinische Klinik" }, { value: "a-1", label: "Medizinische Klinik › Kardiologie" }]} />
    <output data-testid="value">{value}</output>
  </>;
}

describe("SearchSelect", () => {
  it("tippen filtert, Pfeiltasten und Enter wählen, Maus wählt", async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);
    const box = screen.getByRole("combobox", { name: "Übergeordnete Einheit" });
    expect(box).toHaveValue("Keine – direkt im Krankenhaus");
    await user.click(box);
    expect(screen.getAllByRole("option")).toHaveLength(3);
    expect(await axe(container)).toHaveNoViolations();
    await user.type(box, "kardio");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    await user.keyboard("{Enter}");
    expect(screen.getByTestId("value")).toHaveTextContent("a-1");
    expect(box).toHaveValue("Medizinische Klinik › Kardiologie");
    await user.click(box);
    await user.click(screen.getByRole("option", { name: "Keine – direkt im Krankenhaus" }));
    expect(screen.getByTestId("value")).toBeEmptyDOMElement();
  });
});
