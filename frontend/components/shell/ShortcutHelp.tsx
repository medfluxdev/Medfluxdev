"use client";

import Dialog from "@/components/ui/Dialog";
import { SHORTCUTS } from "./useShortcuts";

export default function ShortcutHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} title="Tastenkürzel" onClose={onClose} actions={<button type="button" className="btn btn-primary" onClick={onClose}>Schließen</button>}>
      <table className="data-table">
        <caption className="visually-hidden">Tastenkürzel</caption>
        <thead><tr><th scope="col">Taste</th><th scope="col">Wirkung</th></tr></thead>
        <tbody>{SHORTCUTS.map((item) => <tr key={item.keys}><td><kbd>{item.keys}</kbd></td><td>{item.label}</td></tr>)}</tbody>
      </table>
    </Dialog>
  );
}
