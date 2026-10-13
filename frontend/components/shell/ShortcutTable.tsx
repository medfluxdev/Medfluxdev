import { SHORTCUT_GROUPS, SHORTCUTS } from "./useShortcuts";

/** Tastenkürzel nach Gruppen (Dialog „?“ und Hilfe-Seite). Mit `query` nur passende Zeilen. */
export default function ShortcutTable({ query = "" }: { query?: string }) {
  const term = query.trim().toLocaleLowerCase("de");
  const rows = SHORTCUTS.filter((item) => !term || `${item.keys} ${item.label} ${item.group}`.toLocaleLowerCase("de").includes(term));
  if (!rows.length) return null;
  return <table className="data-table shortcut-table">
    <caption className="visually-hidden">Tastenkürzel</caption>
    <thead><tr><th scope="col">Taste</th><th scope="col">Wirkung</th></tr></thead>
    {SHORTCUT_GROUPS.map((group) => {
      const items = rows.filter((item) => item.group === group);
      return items.length ? <tbody key={group}>
        <tr><th scope="rowgroup" colSpan={2} className="shortcut-group">{group}</th></tr>
        {items.map((item) => <tr key={item.keys}><td><kbd>{item.keys}</kbd></td><td>{item.label}</td></tr>)}
      </tbody> : null;
    })}
  </table>;
}
