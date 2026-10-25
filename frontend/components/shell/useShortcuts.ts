"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { readPreferences, stepTextSize, writePreferences } from "./preferences";

export type ShortcutGroup = "Überall" | "Springen" | "Bearbeiten" | "Bedienung";

/** Einzige Liste der Tastenkürzel: Dialog „?“ und Hilfe-Seite lesen beide von hier. */
export const SHORTCUTS: { keys: string; label: string; group: ShortcutGroup }[] = [
  { keys: "Strg + K", label: "Suche und Befehle öffnen", group: "Überall" },
  { keys: "/", label: "Suche öffnen", group: "Überall" },
  { keys: "?", label: "Tastenkürzel anzeigen", group: "Überall" },
  { keys: "Esc", label: "Dialog oder Seitenleiste schließen", group: "Überall" },
  { keys: "Strg + Alt + + / −", label: "Darstellung größer / kleiner (eigene Größe der Anwendung)", group: "Überall" },
  { keys: "Strg + Alt + 0", label: "Darstellung auf Normal (100 %) zurücksetzen", group: "Überall" },
  { keys: "g dann s", label: "Mein Tag", group: "Springen" },
  { keys: "g dann v", label: "Vertragsliste", group: "Springen" },
  { keys: "g dann t", label: "Fristen & Aufgaben", group: "Springen" },
  { keys: "g dann p", label: "Benachrichtigungen", group: "Springen" },
  { keys: "g dann d", label: "Stammdaten", group: "Springen" },
  { keys: "g dann h", label: "Hilfe", group: "Springen" },
  { keys: "e", label: "Bearbeiten im aktuellen Kasten (wo verfügbar)", group: "Bearbeiten" },
  { keys: "Strg + S", label: "Formular speichern (wo verfügbar)", group: "Bearbeiten" },
  { keys: "← / →", label: "Zwischen Reitern wechseln, wenn ein Reiter den Fokus hat", group: "Bedienung" },
  { keys: "Pos1 / Ende", label: "Zum ersten bzw. letzten Reiter", group: "Bedienung" },
  { keys: "↑ / ↓, Enter", label: "In der Suche (Strg + K) auswählen und öffnen", group: "Bedienung" },
];

export const SHORTCUT_GROUPS: ShortcutGroup[] = ["Überall", "Springen", "Bearbeiten", "Bedienung"];

const ROUTES: Record<string, string> = { s: "/", v: "/register", t: "/fristen", p: "/postfach", d: "/stammdaten", h: "/hilfe" };

function typing(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element && (element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)));
}

/**
 * „Bearbeiten“ per Taste E: Knöpfe mit `data-shortcut="edit"`. Vorrang hat der Kasten mit dem Fokus,
 * sonst der oberste Kasten, dessen Knopf gerade im Bild ist.
 */
export function triggerEditShortcut(): boolean {
  const buttons = [...document.querySelectorAll<HTMLButtonElement>("button[data-shortcut='edit']")]
    .filter((button) => !button.disabled && (typeof button.checkVisibility === "function" ? button.checkVisibility() : !button.closest("[hidden]")));
  if (!buttons.length) return false;
  const active = document.activeElement;
  const inBox = active && active !== document.body
    ? buttons.find((button) => button.closest("section")?.contains(active))
    : undefined;
  const visible = buttons.find((button) => {
    const rect = button.getBoundingClientRect();
    return rect.bottom >= 0 && rect.top < window.innerHeight;
  });
  const target = inBox ?? visible;
  if (!target) return false;
  const section = target.closest("section");
  target.click();
  // Nach dem Umschalten in den Bearbeitungsmodus gleich ins erste Feld.
  window.setTimeout(() => section?.querySelector<HTMLElement>("input:not([type=hidden]):not(:disabled), select:not(:disabled), textarea:not(:disabled)")?.focus(), 50);
  return true;
}

// Globale Tastenkuerzel; in Eingabefeldern nur Strg+K.
export function useShortcuts(openPalette: () => void, openHelp: () => void) {
  const router = useRouter();
  const pendingG = useRef(0);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openPalette();
        return;
      }
      // Eigene Größe der Anwendung (der Browser-Zoom mit Strg + Plus/Minus bleibt unberührt).
      if ((event.ctrlKey || event.metaKey) && event.altKey && ["+", "=", "-", "_", "0"].includes(event.key)) {
        event.preventDefault();
        const prefs = readPreferences();
        const next = event.key === "0" ? "normal" : stepTextSize(prefs.textSize, event.key === "-" || event.key === "_" ? -1 : 1);
        if (next !== prefs.textSize) writePreferences({ ...prefs, textSize: next });
        return;
      }
      if (typing(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "/") { event.preventDefault(); openPalette(); return; }
      if (event.key === "?") { event.preventDefault(); openHelp(); return; }
      if (event.key === "e" && Date.now() - pendingG.current >= 1200 && triggerEditShortcut()) { event.preventDefault(); return; }
      if (event.key === "g") { pendingG.current = Date.now(); return; }
      if (pendingG.current && Date.now() - pendingG.current < 1200 && ROUTES[event.key]) {
        pendingG.current = 0;
        router.push(ROUTES[event.key]);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openHelp, openPalette, router]);
}
