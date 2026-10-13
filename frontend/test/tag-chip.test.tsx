import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import TagChip, { PersonTag, type TagKind } from "@/components/ui/TagChip";

describe("TagChip", () => {
  const kinds: TagKind[] = ["type", "partner", "department", "cost", "device"];

  it("jede Art hat Kennfarbe, Symbol und Wort; ohne Verstöße (axe)", async () => {
    const { container } = render(<div>{kinds.map((kind) => <TagChip key={kind} kind={kind}>{`Wert ${kind}`}</TagChip>)}</div>);
    for (const kind of kinds) {
      const chip = screen.getByText(`Wert ${kind}`);
      expect(chip).toHaveClass("tag-chip", `tag-chip--${kind}`);
      expect(chip.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    }
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Kostenstelle: Nummer in Mono vor dem Namen, Präfix nur für Screenreader", () => {
    render(<TagChip kind="cost" code="950000" srLabel="Kostenstelle">Radiologie</TagChip>);
    const code = screen.getByText("950000");
    expect(code).toHaveClass("tag-chip-code", "mono");
    expect(code.closest(".tag-chip")).toHaveTextContent("Kostenstelle: 950000 Radiologie");
    expect(screen.getByText("Kostenstelle:", { exact: false })).toHaveClass("sr-only");
  });

  it("als Knopf bzw. Link bedienbar, sonst nur Text", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const { container } = render(<>
      <TagChip kind="type" as="button" srLabel="Vertragstyp" onClick={onClick}>Wartungsvertrag</TagChip>
      <TagChip kind="partner" as="link" href="/stammdaten/vertragspartner?id=p-1" srLabel="Vertragspartner">Siemens</TagChip>
      <TagChip kind="device">CT</TagChip>
    </>);
    await user.click(screen.getByRole("button", { name: "Vertragstyp: Wartungsvertrag" }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Vertragspartner: Siemens" })).toHaveAttribute("href", "/stammdaten/vertragspartner?id=p-1");
    expect(screen.getByText("CT").tagName).toBe("SPAN");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("PersonTag: Initiale dekorativ, Name ist die Bedeutung", () => {
    render(<PersonTag name="developer" />);
    const avatar = screen.getByText("D");
    expect(avatar).toHaveAttribute("aria-hidden", "true");
    expect(avatar.closest(".tag-person")).toHaveTextContent("Ddeveloper");
  });
});
