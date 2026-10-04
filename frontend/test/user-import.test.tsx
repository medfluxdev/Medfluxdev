import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import UserImport from "@/components/users/UserImport";
import { generatePassword, parseUserCsv } from "@/lib/user-import-csv";

const api = vi.hoisted(() => ({ importUsers: vi.fn() }));
vi.mock("@/lib/domain-api/users", () => api);

const CSV = "﻿E-Mail;Name;Rolle;Krankenhaus;Bereich;Erstpasswort\r\nanna@klinik.invalid;\"Berg; Anna\";Vertragsmanager;KN;Radiologie;Testpasswort-0001\r\nben@klinik.invalid;Ben Kurz;Leser;KS;;\r\n";

function file(text: string) {
  return new File([text], "benutzer.csv", { type: "text/csv" });
}

describe("CSV-Benutzerliste", () => {
  it("erkennt Trennzeichen, Anführungszeichen und deutsche Spaltennamen", () => {
    const { rows, error } = parseUserCsv(CSV);
    expect(error).toBeNull();
    expect(rows).toEqual([
      { email: "anna@klinik.invalid", display_name: "Berg; Anna", role: "Vertragsmanager", hospital: "KN", department: "Radiologie", password: "Testpasswort-0001" },
      { email: "ben@klinik.invalid", display_name: "Ben Kurz", role: "Leser", hospital: "KS", department: null, password: "" },
    ]);
    expect(parseUserCsv("email,name\nx@y.invalid,X").rows[0]).toMatchObject({ email: "x@y.invalid", display_name: "X" });
    expect(parseUserCsv("Rolle;Krankenhaus\nLeser;KN").error).toBe("Spalte fehlt: E-Mail, Name.");
  });

  it("erzeugt lange, zufällige Erstpasswörter", () => {
    const a = generatePassword();
    expect(a).toHaveLength(16);
    expect(generatePassword()).not.toBe(a);
  });
});

describe("Benutzer-Massenimport", () => {
  beforeEach(() => api.importUsers.mockReset());

  it("prüft erst, zeigt Fehler je Zeile und legt erst nach fehlerfreier Prüfung an", async () => {
    const user = userEvent.setup();
    const onImported = vi.fn();
    api.importUsers
      .mockResolvedValueOnce({ valid: false, created: 0, errors: [], rows: [
        { line: 1, email: "anna@klinik.invalid", display_name: "Berg; Anna", role: "contract_manager", hospital: "Klinikum Nord", department: "Radiologie", errors: [] },
        { line: 2, email: "ben@klinik.invalid", display_name: "Ben Kurz", role: "viewer", hospital: "Klinikum Süd", department: null, errors: ["Erstpasswort fehlt."] },
      ] })
      .mockResolvedValueOnce({ valid: true, created: 0, errors: [], rows: [
        { line: 1, email: "anna@klinik.invalid", display_name: "Berg; Anna", role: "contract_manager", hospital: "Klinikum Nord", department: "Radiologie", errors: [] },
        { line: 2, email: "ben@klinik.invalid", display_name: "Ben Kurz", role: "viewer", hospital: "Klinikum Süd", department: null, errors: [] },
      ] })
      .mockResolvedValueOnce({ valid: true, created: 2, errors: [], rows: [] });

    const { container } = render(<UserImport organizationSlug="test-klinik" onImported={onImported} />);
    await user.upload(screen.getByLabelText("Liste auswählen"), file(CSV));
    expect(await screen.findByText("2 Benutzer in der Liste")).toBeInTheDocument();
    const create = screen.getByRole("button", { name: "2 Benutzer anlegen" });
    expect(create).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Liste prüfen" }));
    expect(api.importUsers).toHaveBeenLastCalledWith("test-klinik", expect.any(Array), true);
    const benRow = screen.getByRole("rowheader", { name: "ben@klinik.invalid" }).closest("tr")!;
    expect(within(benRow).getByText("Erstpasswort fehlt.")).toBeInTheDocument();
    expect(screen.getByText(/1 mit Fehlern/)).toBeInTheDocument();
    expect(create).toBeDisabled();
    expect(await axe(container)).toHaveNoViolations();

    // Admin vergibt das fehlende Passwort selbst; jede Aenderung verlangt eine neue Pruefung.
    await user.type(screen.getByLabelText("Erstpasswort für ben@klinik.invalid"), "Testpasswort-0002");
    expect(screen.getAllByText("noch nicht geprüft")).toHaveLength(2);
    expect(create).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Liste prüfen" }));
    await waitFor(() => expect(create).toBeEnabled());

    await user.click(create);
    const sent = api.importUsers.mock.calls[2];
    expect(sent[2]).toBe(false);
    expect(sent[1][1].password).toBe("Testpasswort-0002");
    expect(await screen.findByText(/2 Benutzer angelegt/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zugangsdaten herunterladen" })).toBeInTheDocument();
    expect(onImported).toHaveBeenCalled();
  });

  it("erzeugt fehlende Passwörter auf Wunsch und blendet sie ein", async () => {
    const user = userEvent.setup();
    render(<UserImport organizationSlug="test-klinik" onImported={vi.fn()} />);
    await user.upload(screen.getByLabelText("Liste auswählen"), file(CSV));
    const ben = await screen.findByLabelText("Erstpasswort für ben@klinik.invalid");
    expect(ben).toHaveAttribute("type", "password");
    expect(ben).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Fehlende Passwörter erzeugen" }));
    expect(screen.getByLabelText("Erstpasswort für ben@klinik.invalid")).toHaveAttribute("type", "text");
    expect((screen.getByLabelText("Erstpasswort für ben@klinik.invalid") as HTMLInputElement).value).toHaveLength(16);
    expect(screen.getByLabelText("Erstpasswort für anna@klinik.invalid")).toHaveValue("Testpasswort-0001");
  });

  it("meldet eine unbrauchbare Datei verständlich", async () => {
    const user = userEvent.setup();
    render(<UserImport organizationSlug="test-klinik" onImported={vi.fn()} />);
    await user.upload(screen.getByLabelText("Liste auswählen"), file("nur eine Zeile"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Kopfzeile und mindestens einen Benutzer");
  });
});
