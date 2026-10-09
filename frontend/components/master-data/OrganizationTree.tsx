"use client";

import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { DEPARTMENT_UNIT_TYPE_LABELS, type DepartmentDto } from "@/lib/domain-api/organizations";
import { buildDepartmentTree, type DepartmentTreeNode } from "@/lib/organization-tree";
import type { OrganizationContext } from "./definitions/organization";
import type { ManagerApi } from "./types";

function Branch({ nodes, context, api }: { nodes: DepartmentTreeNode[]; context: OrganizationContext; api: ManagerApi<DepartmentDto> }) {
  return <ul className="md-tree">
    {nodes.map((node) => {
      const centers = context.costCenters.filter((item) => item.department_id === node.id && item.is_active);
      return <li key={node.id} className={node.is_active ? undefined : "is-inactive"}>
        <div className="md-tree-node">
          <span className="md-tree-title">
            <strong>{node.name}</strong>
            <small><code>{node.code}</code>{node.unit_type ? ` · ${DEPARTMENT_UNIT_TYPE_LABELS[node.unit_type]}` : ""}{node.is_active ? "" : " · deaktiviert"}</small>
            {centers.length ? <small>Kostenstellen: {centers.map((item) => item.code).join(", ")}</small> : null}
          </span>
          <span className="btn-group">
            <Button size="sm" onClick={() => api.openEdit(node)} aria-label={`${node.name} ${api.canEdit ? "bearbeiten" : "ansehen"}`}>{api.canEdit ? "Bearbeiten" : "Ansehen"}</Button>
            {api.canEdit && node.is_active ? <Button size="sm" onClick={() => api.openCreate({ hospital_id: node.hospital_id, parent_id: node.id })} aria-label={`Untereinheit unter ${node.name} anlegen`}>+ Untereinheit</Button> : null}
          </span>
        </div>
        {node.children.length ? <Branch nodes={node.children} context={context} api={api} /> : null}
      </li>;
    })}
  </ul>;
}

// Struktur je Krankenhaus: Klinik › Abteilung › Station, mit Kostenstellen.
export default function OrganizationTree({ rows, context, api }: { rows: DepartmentDto[]; context: OrganizationContext; api: ManagerApi<DepartmentDto> }) {
  const hospitals = context.hospitals.filter((hospital) => rows.some((row) => row.hospital_id === hospital.id) || hospital.is_active);
  if (hospitals.length === 0) return <EmptyState>Noch keine Krankenhäuser angelegt. Legen Sie zuerst ein Krankenhaus an.</EmptyState>;
  return <div className="md-tree-root">
    {hospitals.map((hospital) => {
      const tree = buildDepartmentTree(rows, hospital.id);
      return <section key={hospital.id} className="md-tree-hospital" aria-label={hospital.name}>
        <div className="md-tree-head">
          <h3>{hospital.name} <small><code>{hospital.code}</code></small></h3>
          {api.canEdit && hospital.is_active ? <Button size="sm" onClick={() => api.openCreate({ hospital_id: hospital.id, parent_id: "" })}>+ Einheit</Button> : null}
        </div>
        {tree.length ? <Branch nodes={tree} context={context} api={api} /> : <p className="field-hint">Keine passenden Einheiten.</p>}
      </section>;
    })}
  </div>;
}
