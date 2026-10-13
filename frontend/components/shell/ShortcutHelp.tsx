"use client";

import Link from "next/link";
import Dialog from "@/components/ui/Dialog";
import ShortcutTable from "./ShortcutTable";

export default function ShortcutHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog
      open={open}
      title="Tastenkürzel"
      onClose={onClose}
      actions={<>
        <Link className="btn" href="/hilfe#tastenkuerzel" onClick={onClose}>Zur Hilfe</Link>
        <button type="button" className="btn btn-primary" onClick={onClose}>Schließen</button>
      </>}
    >
      <ShortcutTable />
    </Dialog>
  );
}
