import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import ReviewQueueNav from "@/components/contracts/detail/ReviewQueueNav";
import { REVIEW_QUEUE_KEY } from "@/lib/review-queue";

describe("Prüfreihenfolge (U5)", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("führt zum nächsten und vorherigen Vertrag aus „Zu prüfen“", () => {
    window.sessionStorage.setItem(REVIEW_QUEUE_KEY, JSON.stringify(["a", "b", "c"]));
    render(<ReviewQueueNav contractId="b" />);
    expect(screen.getByText("Vertrag 2 von 3 aus „Zu prüfen“")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Weiter zum nächsten Vertrag" })).toHaveAttribute("href", "/contracts/c?tab=documents&subtab=review");
    expect(screen.getByRole("link", { name: "Zurück" })).toHaveAttribute("href", "/contracts/a?tab=documents&subtab=review");
  });

  it("bietet am Ende den Weg zurück zur Liste und zeigt ohne Reihenfolge nichts", () => {
    window.sessionStorage.setItem(REVIEW_QUEUE_KEY, JSON.stringify(["a", "b"]));
    const { unmount } = render(<ReviewQueueNav contractId="b" />);
    expect(screen.getByRole("link", { name: "Zurück zur Liste" })).toHaveAttribute("href", "/register?ansicht=review");
    unmount();
    window.sessionStorage.clear();
    const { container } = render(<ReviewQueueNav contractId="b" />);
    expect(container).toBeEmptyDOMElement();
  });
});
