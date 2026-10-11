import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import CapturedSources from "@/components/contracts/detail/CapturedSources";

const api = vi.hoisted(() => ({ getContractRegister: vi.fn() }));
vi.mock("@/lib/domain-api/register", () => api);

describe("Aus dem Text übernommen", () => {
  it("listet übernommene Werte mit Seite und Zitat und springt zur Fundstelle", async () => {
    const user = userEvent.setup();
    const onShow = vi.fn();
    const source = { document_version_id: "v-1", page: 3, quote: "Die Kündigungsfrist beträgt drei Monate" };
    api.getContractRegister.mockResolvedValue({ fields: {
      notice_period_value: { label: "Kündigungsfrist", value: 3, display: "3 Monate", document_source: source, updated_by_name: "Maria Becker", updated_at: null },
      short_description: { label: "Kurzbeschreibung", value: "Wartung", display: "Wartung", document_source: null },
    } });
    const { container } = render(<CapturedSources contractId="c-1" orgSlug="test-klinik" onShow={onShow} />);
    expect(await screen.findByRole("heading", { name: "Aus dem Text übernommen (1)" })).toBeInTheDocument();
    expect(screen.getByText(/„Die Kündigungsfrist beträgt drei Monate“/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Fundstelle von Kündigungsfrist zeigen (Seite 3)" }));
    expect(onShow).toHaveBeenCalledWith(source);
  });

  it("ohne übernommene Werte nichts", async () => {
    api.getContractRegister.mockResolvedValue({ fields: {} });
    const { container } = render(<CapturedSources contractId="c-1" orgSlug="test-klinik" onShow={vi.fn()} compact />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(container).toBeEmptyDOMElement();
  });
});
