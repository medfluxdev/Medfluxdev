"use client";

import { useEffect, useState } from "react";
import { usePreferences } from "./preferences";

const DARK_QUERY = "(prefers-color-scheme: dark)";

// Schalter Hell/Dunkel; bei "Wie System" zeigt er das gerade sichtbare Design.
export default function ThemeToggle({ className }: { className?: string }) {
  const [prefs, updatePrefs] = usePreferences();
  const [systemDark, setSystemDark] = useState(false);

  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY);
    if (!media) return;
    setSystemDark(media.matches);
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const dark = prefs.theme === "dark" || (prefs.theme === "system" && systemDark);

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label="Dunkles Design"
      title={dark ? "Zu hellem Design wechseln" : "Zu dunklem Design wechseln"}
      className={`btn btn-ghost btn-icon theme-toggle${className ? ` ${className}` : ""}`}
      onClick={() => updatePrefs({ theme: dark ? "light" : "dark" })}
    >
      {dark ? (
        <svg viewBox="0 0 24 24" aria-hidden="true" className="shell-icon"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      ) : (
        <svg viewBox="0 0 24 24" aria-hidden="true" className="shell-icon"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" /></svg>
      )}
    </button>
  );
}
