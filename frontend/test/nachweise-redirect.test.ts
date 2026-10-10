import { describe, expect, it, vi } from "vitest";

const redirect = vi.hoisted(() => vi.fn((target: string) => { throw new Error(`REDIRECT:${target}`); }));
vi.mock("next/navigation", () => ({ redirect }));

import EvidenceRedirect from "@/app/nachweise/page";

function target(searchParams: Record<string, string>) {
  try {
    EvidenceRedirect({ searchParams });
  } catch (error) {
    return String((error as Error).message).replace("REDIRECT:", "");
  }
  return null;
}

describe("Nachweise sind Teil der Vertragsakte", () => {
  it("führt mit Vertrag zu Dokumente → Nachweise und behält weitere Parameter", () => {
    const id = "01a12543-2d0a-7979-bec9-2f341450d84e";
    expect(target({ contract: id, source_page: "3" })).toBe(`/contracts/${id}?source_page=3&tab=documents&subtab=evidence`);
  });

  it("führt ohne gültigen Vertrag zur Liste „Zu prüfen“", () => {
    expect(target({})).toBe("/register?ansicht=review");
    expect(target({ contract: "../admin" })).toBe("/register?ansicht=review");
  });
});
