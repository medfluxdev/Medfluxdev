"use client";

import { useCallback, useEffect, useState } from "react";

// Darstellung je Benutzer: Design, Textgroesse, Dichte, eingeklappte Seitenleiste.
export type ThemePreference = "system" | "light" | "dark";
export type TextSize = "normal" | "large" | "xlarge";
export type Density = "comfortable" | "compact";

export interface Preferences {
  theme: ThemePreference;
  textSize: TextSize;
  density: Density;
  sidebarCollapsed: boolean;
  /** Nur fuer Entwicklerkonten: Kontext und API-Zeiten in einer Seitenleiste. */
  developerMode: boolean;
}

export const DEFAULT_PREFERENCES: Preferences = { theme: "system", textSize: "normal", density: "comfortable", sidebarCollapsed: false, developerMode: false };
const STORAGE_KEY = "medflux.preferences";
const EVENT = "medflux:preferences";

export function readPreferences(): Preferences {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_PREFERENCES, ...(JSON.parse(raw) as Partial<Preferences>) } : DEFAULT_PREFERENCES;
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function applyPreferences(prefs: Preferences) {
  const root = document.documentElement;
  if (prefs.theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", prefs.theme);
  if (prefs.textSize === "normal") root.removeAttribute("data-text-size");
  else root.setAttribute("data-text-size", prefs.textSize);
  if (prefs.density === "comfortable") root.removeAttribute("data-density");
  else root.setAttribute("data-density", prefs.density);
}

export function writePreferences(prefs: Preferences) {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs)); } catch { /* nur Komfort */ }
  applyPreferences(prefs);
  window.dispatchEvent(new CustomEvent(EVENT, { detail: prefs }));
}

export function usePreferences(): [Preferences, (patch: Partial<Preferences>) => void] {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFERENCES);
  useEffect(() => {
    const current = readPreferences();
    setPrefs(current);
    applyPreferences(current);
    const onChange = (event: Event) => setPrefs((event as CustomEvent<Preferences>).detail);
    window.addEventListener(EVENT, onChange);
    return () => window.removeEventListener(EVENT, onChange);
  }, []);
  const update = useCallback((patch: Partial<Preferences>) => {
    const next = { ...readPreferences(), ...patch };
    setPrefs(next);
    writePreferences(next);
  }, []);
  return [prefs, update];
}

// Vor dem ersten Zeichnen ausfuehren, damit das dunkle Design nicht aufblitzt.
export const PREFERENCES_BOOTSTRAP = `try{var p=JSON.parse(localStorage.getItem("${STORAGE_KEY}")||"{}");var r=document.documentElement;if(p.theme&&p.theme!=="system")r.setAttribute("data-theme",p.theme);if(p.textSize&&p.textSize!=="normal")r.setAttribute("data-text-size",p.textSize);if(p.density==="compact")r.setAttribute("data-density","compact")}catch(e){}`;
