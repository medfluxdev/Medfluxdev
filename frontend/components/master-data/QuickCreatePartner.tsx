"use client";

import { masterDataSection } from "@/lib/master-data";
import { partnerDefinition } from "./definitions/partners";
import QuickCreate from "./QuickCreate";
import type { FormValues } from "./types";

export default function QuickCreatePartner(props: {
  organizationSlug: string;
  open: boolean;
  preset?: FormValues;
  onClose: () => void;
  onCreated: (result: { id: string; label: string }) => void;
}) {
  return <QuickCreate definition={partnerDefinition} section={masterDataSection("vertragspartner")!} {...props} />;
}
