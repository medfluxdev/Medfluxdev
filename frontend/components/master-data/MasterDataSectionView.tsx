"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import { masterDataSection, type MasterDataSection } from "@/lib/master-data";
import { contractCategoryDefinition, contractTypeDefinition, lookupDefinition } from "./definitions/catalogs";
import { costCenterDefinition, departmentDefinition, hospitalDefinition } from "./definitions/organization";
import { partnerDefinition } from "./definitions/partners";
import { deviceTypeDefinition } from "./definitions/deviceTypes";
import { ruleDefinition } from "./definitions/rules";
import EntityManager from "./EntityManager";

// Nur auf ihren Seiten gebraucht: getrennt laden (Leistungsbudget der Stammdaten-Seiten).
const OrganizationTree = dynamic(() => import("./OrganizationTree"), { ssr: false });
const PartnerDuplicates = dynamic(() => import("./PartnerDuplicates"), { ssr: false });
const SupplierWorklist = dynamic(() => import("./SupplierWorklist"), { ssr: false });

function Manager({ section, organizationSlug }: { section: MasterDataSection; organizationSlug: string }) {
  const lookup = useMemo(() => (section.fieldKey ? lookupDefinition(section.fieldKey) : null), [section.fieldKey]);
  switch (section.kind) {
    case "partner":
      return <EntityManager
        definition={partnerDefinition}
        section={section}
        organizationSlug={organizationSlug}
        beforeTable={(api, rows) => <><SupplierWorklist organizationSlug={organizationSlug} api={api} /><PartnerDuplicates organizationSlug={organizationSlug} api={api} rows={rows} /></>}
      />;
    case "hospital":
      return <EntityManager definition={hospitalDefinition} section={section} organizationSlug={organizationSlug} />;
    case "department":
      return <EntityManager
        definition={departmentDefinition}
        section={section}
        organizationSlug={organizationSlug}
        alternateView={{ label: "Struktur", render: (rows, context, api) => <OrganizationTree rows={rows} context={context} api={api} /> }}
      />;
    case "cost_center":
      return <EntityManager definition={costCenterDefinition} section={section} organizationSlug={organizationSlug} />;
    case "contract_type":
      return <EntityManager definition={contractTypeDefinition} section={section} organizationSlug={organizationSlug} />;
    case "contract_category":
      return <EntityManager definition={contractCategoryDefinition} section={section} organizationSlug={organizationSlug} />;
    case "device_type":
      return <EntityManager definition={deviceTypeDefinition} section={section} organizationSlug={organizationSlug} />;
    case "rule":
      return <EntityManager definition={ruleDefinition} section={section} organizationSlug={organizationSlug} />;
    case "lookup":
      return lookup ? <EntityManager definition={lookup} section={section} organizationSlug={organizationSlug} /> : null;
  }
}

export default function MasterDataSectionView({ slug }: { slug: string }) {
  const { organizationSlug } = useAuth();
  const section = masterDataSection(slug);
  if (!section) {
    return <>
      <PageHeader title="Stammdaten" />
      <EmptyState title="Bereich nicht gefunden">Bitte wählen Sie links eine Datenart.</EmptyState>
    </>;
  }
  return <>
    <PageHeader title={section.label} description={section.fieldKey ? "Auswahlliste für Vertragsangaben. Einträge werden deaktiviert, nicht gelöscht." : section.description} />
    {organizationSlug
      ? <Manager key={section.slug} section={section} organizationSlug={organizationSlug} />
      : <p>Bitte zuerst eine Organisation auswählen.</p>}
  </>;
}
