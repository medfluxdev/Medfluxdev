"use client";

import { useEffect, useState } from "react";
import Drawer from "@/components/ui/Drawer";
import InlineAlert from "@/components/ui/InlineAlert";
import Skeleton from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { MasterDataSection } from "@/lib/master-data";
import EntityEditor from "./EntityEditor";
import type { EntityDefinition, FormValues } from "./types";

interface Props<T, C> {
  definition: EntityDefinition<T, C>;
  section: MasterDataSection;
  organizationSlug: string;
  open: boolean;
  preset?: FormValues;
  onClose: () => void;
  onCreated: (result: { id: string; label: string }) => void;
}

// Fehlenden Stammdaten-Eintrag direkt aus einem anderen Formular anlegen
// (gleiches Formular wie in den Stammdaten), ohne die Seite zu verlassen.
export default function QuickCreate<T, C>({ definition, section, organizationSlug, open, preset, onClose, onCreated }: Props<T, C>) {
  const toast = useToast();
  const [context, setContext] = useState<{ value: C } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || context) return;
    let active = true;
    definition.loadContext(organizationSlug)
      .then((value) => { if (active) setContext({ value }); })
      .catch(() => { if (active) setError("Das Formular konnte nicht geladen werden."); });
    return () => { active = false; };
  }, [context, definition, open, organizationSlug]);

  return <Drawer open={open} title={`${definition.singular} anlegen`} onClose={onClose}>
    {error ? <InlineAlert tone="critical" role="alert">{error}</InlineAlert> : null}
    {!context && !error ? <Skeleton lines={4} label="Formular wird geladen…" /> : null}
    {context ? <EntityEditor
      definition={definition}
      context={context.value}
      organizationSlug={organizationSlug}
      row={null}
      preset={preset}
      canEdit
      editorsHint={section.editors}
      canSeeHistory={false}
      onSaved={(result) => {
        toast(`${definition.singular} „${result.label}“ angelegt und ausgewählt.`, "success");
        onCreated({ id: result.id, label: result.label });
      }}
      onCancel={onClose}
    /> : null}
  </Drawer>;
}
