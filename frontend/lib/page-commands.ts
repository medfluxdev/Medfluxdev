"use client";

import { useSyncExternalStore } from "react";

// Befehle, die die aktuelle Seite der Befehlspalette (Strg+K) beisteuert – z. B. „Vertragsbeginn erfassen“
// auf einer Vertragsakte. Die Seite setzt sie beim Anzeigen und leert sie beim Verlassen.

export interface PageCommand {
  id: string;
  label: string;
  hint?: string;
  href: string;
}

const EMPTY: PageCommand[] = [];
let current: PageCommand[] = EMPTY;
const listeners = new Set<() => void>();

export function setPageCommands(items: PageCommand[]) {
  current = items.length ? items : EMPTY;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function usePageCommands(): PageCommand[] {
  return useSyncExternalStore(subscribe, () => current, () => EMPTY);
}
