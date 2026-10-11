/**
 * Einklappen für jeden Kasten im Programm.
 *
 * Statt jede Seite umzubauen, erhält jeder Kasten im Inhaltsbereich (Abschnitt mit Überschrift)
 * einen Knopf in der rechten oberen Ecke. Der Zustand wird je Seite und Kasten im Browser gemerkt.
 * Nur Attribute (`data-box`, `data-collapsed`) und ein eingefügter Knopf: React verwaltet die
 * Klassen der Kästen weiter selbst.
 *
 * Ausgenommen: Kästen mit eigenem Einklappen (`CollapsibleSection`, Klasse `collapsible`) und
 * Kästen mit `data-no-collapse`.
 */

const STORAGE_KEY = "medflux.collapsed-boxes";
const BOX_SELECTOR = [
  "section.cw-section", "div.cw-section", "section.card", "section.panel", "section.detail-card",
  "section.reg-more-section", "section.profile-form-card", "section.profile-security", "section.md-status",
  "section.md-usage", "section.md-hub-admin", "section.rg-panel", "section.user-list",
].join(", ");
const HEADING = /^H[1-4]$/;
const ICON_OPEN = "m6 15 6-6 6 6";
const ICON_CLOSED = "m6 9 6 6 6-6";

function readCollapsed(): Set<string> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function writeCollapsed(keys: Set<string>) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...keys]));
  } catch {
    // Nur Komfort: ohne Speicher bleibt der Kasten offen.
  }
}

/** Seite ohne Kennungen: alle Verträge teilen sich den Zustand ihrer Kästen. */
function pageKey(pathname: string): string {
  return pathname.split("/").map((part) => (/^[0-9a-f-]{8,}$/i.test(part) || /^\d+$/.test(part) ? "*" : part)).join("/");
}

function heading(box: Element): HTMLElement | null {
  const first = box.firstElementChild;
  if (!first) return null;
  if (HEADING.test(first.tagName)) return first as HTMLElement;
  const inner = first.querySelector(":scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > div > h1, :scope > div > h2, :scope > div > h3, :scope > div > h4");
  return inner as HTMLElement | null;
}

/** Überschrift ohne Zähler („Offene Punkte 4“ → „Offene Punkte“), damit Schlüssel und Name stabil bleiben. */
function title(head: HTMLElement): string {
  return (head.textContent ?? "").replace(/\s+/g, " ").replace(/\s*·?\s*\d+$/, "").trim();
}

function boxKey(box: HTMLElement, head: HTMLElement): string {
  return `${pageKey(window.location.pathname)}::${box.id || box.getAttribute("aria-labelledby") || head.id || title(head)}`;
}

function render(box: HTMLElement, button: HTMLButtonElement, collapsed: boolean, name: string) {
  if (collapsed) box.setAttribute("data-collapsed", ""); else box.removeAttribute("data-collapsed");
  button.setAttribute("aria-expanded", String(!collapsed));
  button.setAttribute("aria-label", `${name} ${collapsed ? "aufklappen" : "einklappen"}`);
  button.title = collapsed ? "Aufklappen" : "Einklappen";
  button.querySelector("path")?.setAttribute("d", collapsed ? ICON_CLOSED : ICON_OPEN);
}

function setCollapsed(box: HTMLElement, collapsed: boolean) {
  const button = box.querySelector<HTMLButtonElement>(":scope > .box-toggle");
  const key = box.dataset.boxKey;
  if (!button || !key) return;
  render(box, button, collapsed, box.dataset.boxTitle ?? "Kasten");
  const keys = readCollapsed();
  if (collapsed) keys.add(key); else keys.delete(key);
  writeCollapsed(keys);
}

function enhance(box: HTMLElement, collapsedKeys: Set<string>) {
  if (box.hasAttribute("data-box") || box.classList.contains("collapsible") || box.closest("[data-no-collapse]")) return;
  const head = heading(box);
  if (!head || !title(head)) return;
  const name = title(head);
  const key = boxKey(box, head);
  box.setAttribute("data-box", "");
  box.dataset.boxKey = key;
  box.dataset.boxTitle = name;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-ghost btn-icon btn-sm box-toggle";
  button.innerHTML = `<svg viewBox="4 4 16 16" aria-hidden="true" width="16" height="16"><path d="${ICON_OPEN}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  button.addEventListener("click", () => setCollapsed(box, !box.hasAttribute("data-collapsed")));
  // Direkt nach dem Kopf: in der Tab-Reihenfolge vor dem Inhalt.
  box.firstElementChild!.after(button);
  render(box, button, collapsedKeys.has(key), name);
}

/** Alle Kästen unterhalb von `root` mit dem Einklapp-Knopf versehen (mehrfach aufrufbar). */
export function enhanceBoxes(root: ParentNode) {
  const keys = readCollapsed();
  root.querySelectorAll<HTMLElement>(BOX_SELECTOR).forEach((box) => enhance(box, keys));
}

/** Eingeklappte Kästen um `element` aufklappen (z. B. vor einem Sprung zu einem Abschnitt). */
export function revealBox(element: Element | null) {
  let box = element?.closest<HTMLElement>("[data-collapsed]") ?? null;
  while (box) {
    setCollapsed(box, false);
    box = box.parentElement?.closest<HTMLElement>("[data-collapsed]") ?? null;
  }
}

/** Beobachtet den Inhaltsbereich und versieht neue Kästen; gibt die Aufräumfunktion zurück. */
export function watchBoxes(root: HTMLElement): () => void {
  let frame = 0;
  const run = () => { frame = 0; enhanceBoxes(root); };
  run();
  const observer = new MutationObserver(() => { if (!frame) frame = window.requestAnimationFrame(run); });
  observer.observe(root, { childList: true, subtree: true });
  const onHash = () => revealBox(window.location.hash ? document.getElementById(decodeURIComponent(window.location.hash.slice(1))) : null);
  window.addEventListener("hashchange", onHash);
  return () => {
    observer.disconnect();
    if (frame) window.cancelAnimationFrame(frame);
    window.removeEventListener("hashchange", onHash);
  };
}
