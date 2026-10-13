"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

export const SHORTCUTS: { keys: string; label: string }[] = [
  { keys: "Strg + K", label: "Suche und Befehle öffnen" },
  { keys: "/", label: "Suche öffnen" },
  { keys: "g dann s", label: "Mein Tag" },
  { keys: "g dann v", label: "Vertragsliste" },
  { keys: "g dann t", label: "Fristen & Aufgaben" },
  { keys: "g dann p", label: "Benachrichtigungen" },
  { keys: "g dann d", label: "Stammdaten" },
  { keys: "e", label: "Bearbeiten im aktuellen Kasten (wo verfügbar)" },
  { keys: "Strg + S", label: "Formular speichern (wo verfügbar)" },
  { keys: "?", label: "Diese Übersicht" },
  { keys: "Esc", label: "Dialog oder Seitenleiste schließen" },
];

const ROUTES: Record<string, string> = { s: "/", v: "/register", t: "/fristen", p: "/postfach", d: "/stammdaten" };

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
