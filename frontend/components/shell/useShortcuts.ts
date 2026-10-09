"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

export const SHORTCUTS: { keys: string; label: string }[] = [
  { keys: "Strg + K", label: "Suche und Befehle öffnen" },
  { keys: "/", label: "Suche öffnen" },
  { keys: "g dann s", label: "Mein Tag" },
  { keys: "g dann v", label: "Vertragsliste" },
  { keys: "g dann t", label: "Fristen & Aufgaben" },
  { keys: "g dann p", label: "Postfach" },
  { keys: "g dann d", label: "Stammdaten" },
  { keys: "Strg + S", label: "Formular speichern (wo verfügbar)" },
  { keys: "?", label: "Diese Übersicht" },
  { keys: "Esc", label: "Dialog oder Seitenleiste schließen" },
];

const ROUTES: Record<string, string> = { s: "/", v: "/register", t: "/fristen", p: "/postfach", d: "/stammdaten" };

function typing(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element && (element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)));
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
