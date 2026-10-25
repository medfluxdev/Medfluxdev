"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";

// Darstellung je Benutzer: Design, Textgroesse, Dichte, eingeklappte Seitenleiste.
export type ThemePreference = "system" | "light" | "dark";
export type TextSize = "xsmall" | "small" | "normal" | "large" | "xlarge";
/** Größe für Listen und Tabellen: eigene Stufe oder „same“ (wie die Textgröße). */
export type ListTextSize = TextSize | "same";

export const TEXT_SIZES: { value: TextSize; label: string; percent: number }[] = [
  { value: "xsmall", label: "Sehr klein (80 %)", percent: 80 },
  { value: "small", label: "Klein (87,5 %)", percent: 87.5 },
  { value: "normal", label: "Normal (100 %)", percent: 100 },
  { value: "large", label: "Groß (112,5 %)", percent: 112.5 },
  { value: "xlarge", label: "Sehr groß (125 %)", percent: 125 },
];

/** Seiten, die vor allem Listen und Tabellen zeigen (alles andere, z. B. eine Vertragsakte, gilt als Detailseite). */
export const LIST_PATH = /^\/(register|fristen|analysen|stammdaten|audit|admin|settings|postfach)(\/|$)/;

/** Wirksame Größe: auf Listenseiten die eigene Listengröße, sonst die Textgröße. */
export function effectiveTextSize(prefs: Pick<Preferences, "textSize" | "listTextSize">, pathname: string): TextSize {
  return prefs.listTextSize !== "same" && LIST_PATH.test(pathname) ? prefs.listTextSize : prefs.textSize;
}

/** Einen Schritt kleiner/größer (an den Enden bleibt es stehen). */
export function stepTextSize(current: TextSize, direction: 1 | -1): TextSize {
  const index = TEXT_SIZES.findIndex((item) => item.value === current);
  return TEXT_SIZES[Math.min(TEXT_SIZES.length - 1, Math.max(0, index + direction))].value;
}
export type Density = "comfortable" | "compact";

export interface Preferences {
  theme: ThemePreference;
  textSize: TextSize;
  /** Eigene Größe für Listen und Tabellen („same“ = wie textSize). */
  listTextSize: ListTextSize;
  density: Density;
  sidebarCollapsed: boolean;
  /** Nur fuer Entwicklerkonten: Kontext und API-Zeiten in einer Seitenleiste. */
  developerMode: boolean;
}

// Hell ist Standard; Dunkel und "Wie System" bleiben jederzeit waehlbar.
export const DEFAULT_PREFERENCES: Preferences = { theme: "light", textSize: "normal", listTextSize: "same", density: "comfortable", sidebarCollapsed: false, developerMode: false };
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
  const size = effectiveTextSize(prefs, window.location.pathname);
  if (size === "normal") root.removeAttribute("data-text-size");
  else root.setAttribute("data-text-size", size);
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
  const pathname = usePathname();
  // Beim Seitenwechsel gilt je nach Seite die Text- oder die Listengröße.
  useEffect(() => { applyPreferences(readPreferences()); }, [pathname]);
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

// U8: Serverkopie, damit die Darstellung dem Benutzer auf andere Geraete folgt.
// localStorage bleibt der schnelle Weg (kein Aufblitzen); der Server gewinnt beim Anmelden.
interface ServerPreferences {
  theme: ThemePreference;
  text_size: TextSize;
  list_text_size?: ListTextSize;
  density: Density;
  sidebar_collapsed: boolean;
  developer_mode: boolean;
}

function toServer(prefs: Preferences): ServerPreferences {
  return { theme: prefs.theme, text_size: prefs.textSize, list_text_size: prefs.listTextSize, density: prefs.density, sidebar_collapsed: prefs.sidebarCollapsed, developer_mode: prefs.developerMode };
}

function fromServer(value: ServerPreferences): Preferences {
  return { theme: value.theme, textSize: value.text_size, listTextSize: value.list_text_size ?? "same", density: value.density, sidebarCollapsed: value.sidebar_collapsed, developerMode: value.developer_mode };
}

const SYNC_DELAY_MS = 600;

export function useServerPreferenceSync(accountId: string | null) {
  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    let ready = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const save = (prefs: Preferences) => { void apiPut("/api/profile/preferences", toServer(prefs)).catch(() => undefined); };
    apiGet<{ preferences: ServerPreferences | null }>("/api/profile/preferences")
      .then((result) => {
        if (cancelled) return;
        if (result.preferences) writePreferences(fromServer(result.preferences));
        else save(readPreferences());
      })
      .catch(() => undefined)
      .finally(() => { ready = true; });
    const onChange = (event: Event) => {
      if (!ready) return;
      const prefs = (event as CustomEvent<Preferences>).detail;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => save(prefs), SYNC_DELAY_MS);
    };
    window.addEventListener(EVENT, onChange);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      window.removeEventListener(EVENT, onChange);
    };
  }, [accountId]);
}

// Vor dem ersten Zeichnen ausfuehren, damit kein falsches Design aufblitzt.
export const PREFERENCES_BOOTSTRAP = `try{var p=JSON.parse(localStorage.getItem("${STORAGE_KEY}")||"{}");var r=document.documentElement;var t=p.theme||"light";if(t!=="system")r.setAttribute("data-theme",t);var s=p.textSize;if(p.listTextSize&&p.listTextSize!=="same"&&/^\\/(register|fristen|analysen|stammdaten|audit|admin|settings|postfach)(\\/|$)/.test(location.pathname))s=p.listTextSize;if(s&&s!=="normal")r.setAttribute("data-text-size",s);if(p.density==="compact")r.setAttribute("data-density","compact")}catch(e){}`;
