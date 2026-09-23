"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const sections = [
  ["allgemein", "Allgemein"], ["lokale-ki", "Lokale KI"],
  ["dokumente", "Dokumentenverarbeitung"], ["speicher", "Speicher & Daten"],
  ["sicherheit", "Benutzer & Sicherheit"], ["diagnose", "System & Diagnose"],
] as const;

export default function SettingsNavigation() {
  const [active, setActive] = useState("allgemein");
  const navigating = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const go = useCallback((id: string, smooth: boolean, focus: boolean) => {
    const target = document.getElementById(`settings-${id}`);
    if (!target) return;
    setActive(id);
    navigating.current = true;
    const offset = (document.querySelector(".topbar")?.getBoundingClientRect().height ?? 76) + 20;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (focus) target.focus({ preventScroll: true });
    window.scrollTo({ top: Math.max(0, window.scrollY + target.getBoundingClientRect().top - offset),
      behavior: smooth && !reduced ? "smooth" : "auto" });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { navigating.current = false; }, 700);
  }, []);

  useEffect(() => {
    const hash = () => {
      const id = window.location.hash.replace(/^#settings-/, "");
      if (sections.some(([key]) => key === id)) go(id, false, false);
      else if (!window.location.hash) go("allgemein", false, false);
    };
    let frame = 0;
    const scroll = () => {
      if (navigating.current || frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const offset = (document.querySelector(".topbar")?.getBoundingClientRect().height ?? 76) + 40;
        let current: string = sections[0][0];
        for (const [id] of sections) {
          if ((document.getElementById(`settings-${id}`)?.getBoundingClientRect().top ?? Infinity) <= offset) current = id;
        }
        if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) current = "diagnose";
        setActive(current);
      });
    };
    const initial = requestAnimationFrame(() => { if (window.location.hash) hash(); });
    const cancel = () => { navigating.current = false; };
    window.addEventListener("hashchange", hash);
    window.addEventListener("popstate", hash);
    window.addEventListener("scroll", scroll, { passive: true });
    window.addEventListener("wheel", cancel, { passive: true });
    window.addEventListener("touchstart", cancel, { passive: true });
    return () => {
      cancelAnimationFrame(initial); cancelAnimationFrame(frame); clearTimeout(timer.current);
      window.removeEventListener("hashchange", hash); window.removeEventListener("popstate", hash);
      window.removeEventListener("scroll", scroll); window.removeEventListener("wheel", cancel);
      window.removeEventListener("touchstart", cancel);
    };
  }, [go]);

  return <nav className="settings-navigation" aria-label="Einstellungsbereiche">
    <ul className="settings-nav">{sections.map(([id, label]) => <li key={id}>
      <a href={`#settings-${id}`} aria-current={active === id ? "location" : undefined}
        onClick={(event) => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
          event.preventDefault();
          const hash = `#settings-${id}`;
          if (window.location.hash !== hash) window.history.pushState(null, "", hash);
          go(id, true, true);
        }}>{label}</a>
    </li>)}</ul>
  </nav>;
}
