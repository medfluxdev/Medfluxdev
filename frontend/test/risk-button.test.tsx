import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RiskButton from "@/components/contracts/detail/RiskButton";

const api = vi.hoisted(() => ({ apiPost: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), apiPost: api.apiPost }));

const WARNINGS = [
  { warning_type: "missing_cancellation_date", severity: "high", title_de: "Kündigungsfrist fehlt", target_kind: null, target_date: null, days_remaining: null, requires_action: true, requires_review: false, action_state: null },
  { warning_type: "info_only", severity: "info", title_de: "Nur Hinweis", target_kind: null, target_date: null, days_remaining: null, requires_action: false, requires_review: false, action_state: null },
];
const HIGH = { computed: "high", effective: "high", override: null, confirmed: null };

beforeEach(() => { vi.clearAllMocks(); api.apiPost.mockResolvedValue({}); });

describe("Risiko im Kopf", () => {
  it("zeigt, woher die Einschätzung kommt, und bestätigt sie", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    const { container } = render(<RiskButton contractId="c-1" orgSlug="k" risk={HIGH} warnings={WARNINGS} canEdit onChanged={onChanged} />);
    await user.click(screen.getByRole("button", { name: /Risiko hoch/ }));
    const panel = screen.getByRole("group", { name: "Risiko des Vertrags" });
    expect(within(panel).getByText("Berechnet: Risiko hoch")).toBeInTheDocument();
    expect(within(panel).getByText("Kündigungsfrist fehlt")).toBeInTheDocument();
    expect(within(panel).queryByText("Nur Hinweis")).not.toBeInTheDocument(); // Hinweise heben das Risiko nicht
    expect(await axe(container)).toHaveNoViolations();
    await user.click(within(panel).getByRole("button", { name: "Bestätigen" }));
    expect(api.apiPost).toHaveBeenCalledWith("/api/contracts/c-1/risk?organization_slug=k", { action: "confirm" });
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("anders einschätzen braucht eine Begründung; festgelegt zeigt Grund und Zurücksetzen", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<RiskButton contractId="c-1" orgSlug="k" risk={HIGH} warnings={WARNINGS} canEdit onChanged={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Risiko hoch/ }));
    await user.click(screen.getByRole("button", { name: "Anders einschätzen …" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Risiko" }), "low");
    expect(screen.getByRole("button", { name: "Festlegen" })).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "Begründung" }), "Gerät wird ersetzt");
    await user.click(screen.getByRole("button", { name: "Festlegen" }));
    expect(api.apiPost).toHaveBeenCalledWith("/api/contracts/c-1/risk?organization_slug=k", { action: "override", level: "low", reason: "Gerät wird ersetzt" });
    unmount();

    const overridden = { computed: "high", effective: "low", override: { level: "low", reason: "Gerät wird ersetzt", by: "Maria", at: "2026-10-11T10:00:00Z" }, confirmed: null };
    render(<RiskButton contractId="c-1" orgSlug="k" risk={overridden} warnings={WARNINGS} canEdit onChanged={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Risiko niedrig · festgelegt/ }));
    expect(screen.getByText(/Gerät wird ersetzt/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Auf berechneten Wert zurücksetzen" }));
    expect(api.apiPost).toHaveBeenLastCalledWith("/api/contracts/c-1/risk?organization_slug=k", { action: "reset" });
  });

  it("ohne Bearbeitungsrecht nur ansehen; ohne auffälliges Risiko kein Knopf", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<RiskButton contractId="c-1" orgSlug="k" risk={HIGH} warnings={WARNINGS} canEdit={false} onChanged={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Risiko hoch/ }));
    expect(screen.queryByRole("button", { name: "Bestätigen" })).not.toBeInTheDocument();
    unmount();
    const { container } = render(<RiskButton contractId="c-1" orgSlug="k" risk={{ computed: "low", effective: "low", override: null, confirmed: null }} warnings={[]} canEdit onChanged={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
