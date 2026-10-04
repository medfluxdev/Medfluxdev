"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DEPARTMENT_UNIT_TYPE_LABELS,
  createCostCenter,
  createDepartment,
  createHospital,
  getOrganizationStructure,
  listCostCenters,
  searchOrganizationStructure,
  updateCostCenter,
  updateDepartment,
  updateHospital,
  type CostCenterDto,
  type DepartmentDto,
  type DepartmentUnitType,
  type HospitalDto,
  type OrganizationStructureDto,
  type StructureSearchHitDto,
} from "@/lib/domain-api/organizations";

const UNIT_TYPE_OPTIONS = Object.entries(DEPARTMENT_UNIT_TYPE_LABELS ?? {}) as [DepartmentUnitType, string][];

function unitTypeLabel(value?: DepartmentUnitType | null) {
  return value ? (DEPARTMENT_UNIT_TYPE_LABELS ?? {})[value] ?? null : null;
}
import {
  buildDepartmentTree,
  departmentDescendantIds,
  departmentFullPath,
  type DepartmentTreeNode,
} from "@/lib/organization-tree";

function DepartmentBranch({
  nodes,
  departments,
  costCenters,
  editingParentId,
  parentDraft,
  onRename,
  onToggle,
  onAddChild,
  onBeginParentEdit,
  onParentDraftChange,
  onSaveParent,
  onCancelParentEdit,
  onRenameCostCenter,
  onToggleCostCenter,
}: {
  nodes: DepartmentTreeNode[];
  departments: DepartmentDto[];
  costCenters: CostCenterDto[];
  onRenameCostCenter: (center: CostCenterDto) => void;
  onToggleCostCenter: (center: CostCenterDto) => void;
  editingParentId: string | null;
  parentDraft: string;
  onRename: (department: DepartmentDto) => void;
  onToggle: (department: DepartmentDto) => void;
  onAddChild: (department: DepartmentDto) => void;
  onBeginParentEdit: (department: DepartmentDto) => void;
  onParentDraftChange: (value: string) => void;
  onSaveParent: (department: DepartmentDto) => void;
  onCancelParentEdit: () => void;
}) {
  return <ul className="org-department-tree">
    {nodes.map((department) => {
      const path = departmentFullPath(department, departments);
      const descendants = departmentDescendantIds(department.id, departments);
      const parentOptions = departments.filter((candidate) =>
        candidate.hospital_id === department.hospital_id &&
        candidate.is_active &&
        candidate.id !== department.id &&
        !descendants.has(candidate.id)
      );
      const linkedCenters = costCenters.filter((center) => center.department_id === department.id);
      const editing = editingParentId === department.id;

      return <li key={department.id} className={`org-department-node${department.is_active ? "" : " inactive"}`}>
        <div className="org-department-node-card">
          <div className="org-department-node-title">
            <strong>{department.name}</strong>
            <small>{department.code}{unitTypeLabel(department.unit_type) ? ` · ${unitTypeLabel(department.unit_type)}` : ""} · {department.is_active ? "Aktiv" : "Inaktiv"}</small>
            <span className="org-department-full-path">{path}</span>
            {linkedCenters.length ? <span className="org-node-cost-centers">Kostenstellen: {linkedCenters.map((center) => <span key={center.id} className={`org-cost-center-chip${center.is_active ? "" : " inactive"}`}>
              {center.code} – {center.name}{center.is_active ? "" : " (inaktiv)"}
              <button type="button" className="org-chip-button" aria-label={`Kostenstelle ${center.code} bearbeiten`} onClick={() => onRenameCostCenter(center)}>Bearbeiten</button>
              <button type="button" className="org-chip-button" aria-label={`Kostenstelle ${center.code} ${center.is_active ? "deaktivieren" : "aktivieren"}`} onClick={() => onToggleCostCenter(center)}>{center.is_active ? "Deaktivieren" : "Aktivieren"}</button>
            </span>)}</span> : null}
          </div>
          <div className="org-department-node-actions">
            <button type="button" onClick={() => onAddChild(department)}>Untereinheit hinzufügen</button>
            <button type="button" onClick={() => onRename(department)}>Name bearbeiten</button>
            <button type="button" onClick={() => onBeginParentEdit(department)}>Übergeordnete Einheit</button>
            <button type="button" onClick={() => onToggle(department)}>{department.is_active ? "Deaktivieren" : "Aktivieren"}</button>
          </div>
          {editing ? <form className="org-parent-editor" onSubmit={(event) => { event.preventDefault(); onSaveParent(department); }}>
            <label>
              Übergeordnete Einheit
              <select value={parentDraft} onChange={(event) => onParentDraftChange(event.target.value)}>
                <option value="">Keine (Einheit im Krankenhaus)</option>
                {parentOptions.map((option) => <option key={option.id} value={option.id}>{departmentFullPath(option, departments)}</option>)}
              </select>
            </label>
            <button type="submit">Struktur speichern</button>
            <button type="button" className="org-button-secondary" onClick={onCancelParentEdit}>Abbrechen</button>
          </form> : null}
        </div>
        {department.children.length ? <DepartmentBranch
          nodes={department.children}
          departments={departments}
          costCenters={costCenters}
          editingParentId={editingParentId}
          parentDraft={parentDraft}
          onRename={onRename}
          onToggle={onToggle}
          onAddChild={onAddChild}
          onBeginParentEdit={onBeginParentEdit}
          onParentDraftChange={onParentDraftChange}
          onSaveParent={onSaveParent}
          onCancelParentEdit={onCancelParentEdit}
          onRenameCostCenter={onRenameCostCenter}
          onToggleCostCenter={onToggleCostCenter}
        /> : null}
      </li>;
    })}
  </ul>;
}

export default function OrganizationStructureManager({ organizationSlug }: { organizationSlug: string }) {
  const [data, setData] = useState<OrganizationStructureDto>({ hospitals: [], departments: [] });
  const [costCenters, setCostCenters] = useState<CostCenterDto[]>([]);
  const [hospitalName, setHospitalName] = useState("");
  const [hospitalCode, setHospitalCode] = useState("");
  const [hospitalAddress, setHospitalAddress] = useState("");
  const [departmentHospitalId, setDepartmentHospitalId] = useState("");
  const [departmentParentId, setDepartmentParentId] = useState("");
  const [departmentName, setDepartmentName] = useState("");
  const [departmentCode, setDepartmentCode] = useState("");
  const [departmentUnitType, setDepartmentUnitType] = useState<DepartmentUnitType | "">("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<StructureSearchHitDto[]>([]);
  const [searchState, setSearchState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [costCenterHospitalId, setCostCenterHospitalId] = useState("");
  const [costCenterDepartmentId, setCostCenterDepartmentId] = useState("");
  const [costCenterCode, setCostCenterCode] = useState("");
  const [costCenterName, setCostCenterName] = useState("");
  const [editingParentId, setEditingParentId] = useState<string | null>(null);
  const [parentDraft, setParentDraft] = useState("");
  const [message, setMessage] = useState("");
  const departmentFormRef = useRef<HTMLFormElement>(null);
  const departmentNameRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [structure, centers] = await Promise.all([
        getOrganizationStructure(organizationSlug),
        listCostCenters(organizationSlug),
      ]);
      setData(structure);
      setCostCenters(centers.items);
      const firstHospital = structure.hospitals.find((item) => item.is_active)?.id || structure.hospitals[0]?.id || "";
      setDepartmentHospitalId((current) => current || firstHospital);
      setCostCenterHospitalId((current) => current || firstHospital);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Organisationsstruktur konnte nicht geladen werden.");
    }
  }, [organizationSlug]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const query = searchQuery.trim();
    if (query.length < 2) { setSearchHits([]); setSearchState("idle"); return; }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearchState("loading");
      try {
        const result = await searchOrganizationStructure(organizationSlug, query, controller.signal);
        if (!controller.signal.aborted) { setSearchHits(result.items); setSearchState("done"); }
      } catch (err) {
        if (!controller.signal.aborted) { setSearchHits([]); setSearchState("error"); }
      }
    }, 250);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [organizationSlug, searchQuery]);

  const departmentTrees = useMemo(() => new Map(
    data.hospitals.map((hospital) => [hospital.id, buildDepartmentTree(data.departments, hospital.id)]),
  ), [data.departments, data.hospitals]);
  const departmentOptions = useMemo(
    () => data.departments.filter((item) => item.hospital_id === departmentHospitalId && item.is_active),
    [data.departments, departmentHospitalId],
  );
  const costCenterDepartments = useMemo(
    () => data.departments.filter((item) => item.hospital_id === costCenterHospitalId && item.is_active),
    [data.departments, costCenterHospitalId],
  );

  async function submitHospital(event: FormEvent) {
    event.preventDefault();
    try {
      await createHospital(organizationSlug, { name: hospitalName, code: hospitalCode, address: hospitalAddress || null });
      setHospitalName(""); setHospitalCode(""); setHospitalAddress("");
      setMessage("Krankenhaus wurde angelegt.");
      await load();
    } catch (err) { setMessage(err instanceof Error ? err.message : "Krankenhaus konnte nicht angelegt werden."); }
  }

  async function submitDepartment(event: FormEvent) {
    event.preventDefault();
    try {
      await createDepartment(organizationSlug, {
        hospital_id: departmentHospitalId,
        parent_id: departmentParentId || null,
        name: departmentName,
        code: departmentCode,
        ...(departmentUnitType ? { unit_type: departmentUnitType } : {}),
      });
      setDepartmentName(""); setDepartmentCode(""); setDepartmentParentId(""); setDepartmentUnitType("");
      setMessage("Einheit wurde in der Organisationsstruktur angelegt.");
      await load();
    } catch (err) { setMessage(err instanceof Error ? err.message : "Einheit konnte nicht angelegt werden."); }
  }

  async function submitCostCenter(event: FormEvent) {
    event.preventDefault();
    try {
      await createCostCenter(organizationSlug, { hospital_id: costCenterHospitalId, department_id: costCenterDepartmentId || null, code: costCenterCode, name: costCenterName });
      setCostCenterCode(""); setCostCenterName("");
      setMessage("Kostenstelle wurde angelegt.");
      await load();
    } catch (err) { setMessage(err instanceof Error ? err.message : "Kostenstelle konnte nicht angelegt werden."); }
  }

  async function renameHospital(row: HospitalDto) {
    const name = window.prompt("Name des Krankenhauses", row.name);
    if (!name || name === row.name) return;
    try { await updateHospital(organizationSlug, row.id, { name }); setMessage("Krankenhaus wurde aktualisiert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Krankenhaus konnte nicht aktualisiert werden."); }
  }

  async function toggleHospital(row: HospitalDto) {
    try { await updateHospital(organizationSlug, row.id, { is_active: !row.is_active }); setMessage(row.is_active ? "Krankenhaus wurde deaktiviert." : "Krankenhaus wurde aktiviert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Status konnte nicht geändert werden."); }
  }

  async function renameDepartment(row: DepartmentDto) {
    const name = window.prompt("Name der Einheit", row.name);
    if (!name || name === row.name) return;
    try { await updateDepartment(organizationSlug, row.id, { name }); setMessage("Einheit wurde aktualisiert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Einheit konnte nicht aktualisiert werden."); }
  }

  async function toggleDepartment(row: DepartmentDto) {
    try { await updateDepartment(organizationSlug, row.id, { is_active: !row.is_active }); setMessage(row.is_active ? "Einheit wurde deaktiviert." : "Einheit wurde aktiviert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Status konnte nicht geändert werden."); }
  }

  async function renameCostCenter(center: CostCenterDto) {
    const name = window.prompt("Bezeichnung der Kostenstelle", center.name);
    if (!name || name === center.name) return;
    try { await updateCostCenter(organizationSlug, center.id, { name }); setMessage("Kostenstelle wurde aktualisiert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Kostenstelle konnte nicht aktualisiert werden."); }
  }

  async function toggleCostCenter(center: CostCenterDto) {
    try { await updateCostCenter(organizationSlug, center.id, { is_active: !center.is_active }); setMessage(center.is_active ? "Kostenstelle wurde deaktiviert." : "Kostenstelle wurde aktiviert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Status konnte nicht geändert werden."); }
  }

  function selectChild(parent: DepartmentDto) {
    setDepartmentHospitalId(parent.hospital_id);
    setDepartmentParentId(parent.id);
    setDepartmentName("");
    setMessage(`Neue Untereinheit unter „${departmentFullPath(parent, data.departments)}“ anlegen.`);
    const form = departmentFormRef.current;
    if (form && typeof form.scrollIntoView === "function") {
      form.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    departmentNameRef.current?.focus();
  }

  function editParent(department: DepartmentDto) {
    setEditingParentId(department.id);
    setParentDraft(department.parent_id || "");
  }

  async function saveParent(department: DepartmentDto) {
    try {
      await updateDepartment(organizationSlug, department.id, { parent_id: parentDraft || null });
      setEditingParentId(null);
      setParentDraft("");
      setMessage("Organisationsstruktur wurde aktualisiert.");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Organisationsstruktur konnte nicht geändert werden.");
    }
  }

  return <>
    {message ? <div className="org-settings-message" role="status">{message}</div> : null}
    <div className="org-settings-forms">
      <form onSubmit={submitHospital} className="org-settings-card"><h2>Krankenhaus hinzufügen</h2><label>Name<input value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} required /></label><label>Kürzel<input value={hospitalCode} onChange={(e) => setHospitalCode(e.target.value)} required /></label><label>Adresse<input value={hospitalAddress} onChange={(e) => setHospitalAddress(e.target.value)} /></label><button type="submit">Krankenhaus anlegen</button></form>
      <form ref={departmentFormRef} onSubmit={submitDepartment} className="org-settings-card"><h2>Einheit hinzufügen</h2><label>Krankenhaus<select value={departmentHospitalId} onChange={(e) => { setDepartmentHospitalId(e.target.value); setDepartmentParentId(""); }} required><option value="">Bitte wählen</option>{data.hospitals.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Übergeordnete Einheit (optional)<select value={departmentParentId} onChange={(e) => setDepartmentParentId(e.target.value)} disabled={!departmentHospitalId}><option value="">Keine (Einheit im Krankenhaus)</option>{departmentOptions.map((item) => <option key={item.id} value={item.id}>{departmentFullPath(item, data.departments)}</option>)}</select></label><label>Name<input ref={departmentNameRef} value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} required /></label><label>Kürzel<input value={departmentCode} onChange={(e) => setDepartmentCode(e.target.value)} required /></label><label>Einheitentyp (optional)<select value={departmentUnitType} onChange={(e) => setDepartmentUnitType(e.target.value as DepartmentUnitType | "")}><option value="">Nicht festgelegt</option>{UNIT_TYPE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button type="submit" disabled={!departmentHospitalId}>Einheit anlegen</button></form>
      <form onSubmit={submitCostCenter} className="org-settings-card"><h2>Kostenstelle hinzufügen</h2><label>Krankenhaus<select value={costCenterHospitalId} onChange={(e) => { setCostCenterHospitalId(e.target.value); setCostCenterDepartmentId(""); }} required><option value="">Bitte wählen</option>{data.hospitals.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Abteilung<select value={costCenterDepartmentId} onChange={(e) => setCostCenterDepartmentId(e.target.value)} disabled={!costCenterHospitalId}><option value="">Krankenhausweit</option>{costCenterDepartments.map((x) => <option key={x.id} value={x.id}>{departmentFullPath(x, data.departments)}</option>)}</select></label><label>Kostenstelle<input value={costCenterCode} onChange={(e) => setCostCenterCode(e.target.value)} required /></label><label>Bezeichnung<input value={costCenterName} onChange={(e) => setCostCenterName(e.target.value)} required /></label><button type="submit" disabled={!costCenterHospitalId}>Kostenstelle anlegen</button></form>
    </div>
    <section className="org-settings-search" aria-label="Struktur durchsuchen">
      <label>Einheit oder Kostenstelle suchen<input type="search" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="z. B. 471120 oder Kardiologie" /></label>
      {searchState === "loading" ? <p role="status">Suche läuft…</p> : null}
      {searchState === "error" ? <p role="alert">Suche ist fehlgeschlagen.</p> : null}
      {searchState === "done" && searchHits.length === 0 ? <p role="status">Keine Treffer.</p> : null}
      {searchHits.length ? <ul className="org-search-results" aria-label="Suchergebnisse">{searchHits.map((hit) => <li key={`${hit.kind}-${hit.id}`} className={`org-search-hit${hit.is_active ? "" : " inactive"}`}>
        <strong>{hit.code} – {hit.name}</strong>
        <span>{hit.kind === "cost_center" ? "Kostenstelle" : (unitTypeLabel(hit.unit_type) ?? "Einheit")}{hit.is_active ? "" : " · inaktiv"}</span>
        {hit.path_label ? <span className="org-department-full-path">{hit.path_label}</span> : null}
        <small>{hit.hospital_name}</small>
      </li>)}</ul> : null}
    </section>
    <section className="org-settings-list">
      <div className="org-settings-list-head"><h2>Struktur</h2><span>{data.hospitals.length} Krankenhäuser · {data.departments.length} Einheiten · {costCenters.length} Kostenstellen</span></div>
      {data.hospitals.length === 0 ? <p>Noch keine Krankenhäuser angelegt.</p> : data.hospitals.map((hospital) => <article key={hospital.id} className={`org-hospital-row${hospital.is_active ? "" : " inactive"}`}>
        <div className="org-hospital-title"><strong>{hospital.name}</strong><span>{hospital.code}</span>{hospital.address ? <small>{hospital.address}</small> : null}<small>{hospital.is_active ? "Aktiv" : "Inaktiv"}</small></div>
        <div className="org-hospital-structure">
          {(departmentTrees.get(hospital.id) ?? []).length ? <DepartmentBranch
            nodes={departmentTrees.get(hospital.id) ?? []}
            departments={data.departments}
            costCenters={costCenters.filter((center) => center.hospital_id === hospital.id)}
            editingParentId={editingParentId}
            parentDraft={parentDraft}
            onRename={renameDepartment}
            onToggle={toggleDepartment}
            onAddChild={selectChild}
            onBeginParentEdit={editParent}
            onParentDraftChange={setParentDraft}
            onSaveParent={saveParent}
            onCancelParentEdit={() => { setEditingParentId(null); setParentDraft(""); }}
            onRenameCostCenter={renameCostCenter}
            onToggleCostCenter={toggleCostCenter}
          /> : <em>Keine Einheiten</em>}
          {costCenters.filter((center) => center.hospital_id === hospital.id && !center.department_id).map((center) => <span key={center.id} className="org-hospital-cost-center">{center.code} · {center.name} (krankenhausweit)</span>)}
        </div>
        <div className="account-card-actions"><button type="button" onClick={() => void renameHospital(hospital)}>Bearbeiten</button><button type="button" onClick={() => void toggleHospital(hospital)}>{hospital.is_active ? "Deaktivieren" : "Aktivieren"}</button></div>
      </article>)}
    </section>
  </>;
}
