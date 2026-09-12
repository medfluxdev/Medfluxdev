"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

type Item = { id: string; name: string; code: string; is_active: boolean };
type Department = Item & { hospital_id: string };
type Center = Item & { hospital_id: string; department_id: string | null };
type Assignee = { id: string; display_name: string; role: string; hospital_id: string | null; department_id: string | null };
type Assignment = { hospital_id: string | null; department_ids: string[]; cost_center_id: string | null; responsible_account_id: string | null };

export default function ContractOwnershipPanel({ contractId, orgSlug, onSaved }: { contractId: string; orgSlug: string; onSaved?: () => void }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [hospitals, setHospitals] = useState<Item[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [assignees, setAssignees] = useState<Assignee[]>([]);
  const [hospitalId, setHospitalId] = useState("");
  const [departmentIds, setDepartmentIds] = useState<string[]>([]);
  const [centerId, setCenterId] = useState("");
  const [responsibleId, setResponsibleId] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editable) return;
    const q = encodeURIComponent(orgSlug);
    Promise.all([
      apiGet<{ hospitals: Item[]; departments: Department[] }>(`/api/organization-structure?organization_slug=${q}`),
      apiGet<{ items: Center[] }>(`/api/cost-centers?organization_slug=${q}`),
      apiGet<{ items: Assignee[] }>(`/api/ownership/assignees?organization_slug=${q}`),
      apiGet<Assignment>(`/api/ownership/contracts/${contractId}?organization_slug=${q}`),
    ]).then(([structure, costCenters, users, assignment]) => {
      setHospitals(structure.hospitals); setDepartments(structure.departments); setCenters(costCenters.items); setAssignees(users.items);
      setHospitalId(assignment.hospital_id ?? ""); setDepartmentIds(assignment.department_ids ?? []); setCenterId(assignment.cost_center_id ?? ""); setResponsibleId(assignment.responsible_account_id ?? "");
    }).catch(() => setMessage("Zuordnung konnte nicht geladen werden."));
  }, [contractId, editable, orgSlug]);

  const visibleDepartments = useMemo(() => departments.filter((x) => x.is_active && x.hospital_id === hospitalId), [departments, hospitalId]);
  const visibleCenters = useMemo(() => centers.filter((x) => x.is_active && x.hospital_id === hospitalId && (!x.department_id || departmentIds.length === 0 || departmentIds.includes(x.department_id))), [centers, hospitalId, departmentIds]);
  const visibleAssignees = useMemo(() => assignees.filter((x) => (!x.hospital_id || x.hospital_id === hospitalId) && (departmentIds.length === 0 || !x.department_id || departmentIds.includes(x.department_id))), [assignees, hospitalId, departmentIds]);

  function toggleDepartment(id: string) { setDepartmentIds((current) => current.includes(id) ? current.filter((x) => x !== id) : [...current, id]); setCenterId(""); }

  async function save() {
    setSaving(true); setMessage("");
    try {
      await apiPatch(`/api/ownership/contracts/${contractId}?organization_slug=${encodeURIComponent(orgSlug)}`, { hospital_id: hospitalId || null, department_ids: departmentIds, cost_center_id: centerId || null, responsible_account_id: responsibleId || null });
      setMessage("Zuordnung gespeichert."); onSaved?.();
    } catch { setMessage("Zuordnung konnte nicht gespeichert werden."); }
    finally { setSaving(false); }
  }

  if (!editable) return null;
  return <section className="cw-section cw-ownership-section"><div className="cw-section-head"><div><h2>Organisation & Verantwortlichkeit</h2><p>Vertrag organisatorisch zuordnen und eine verantwortliche Person festlegen.</p></div></div><div className="cw-ownership-grid">
    <label><span>Krankenhaus</span><select value={hospitalId} onChange={(e) => { setHospitalId(e.target.value); setDepartmentIds([]); setCenterId(""); }}><option value="">Organisationsweit</option>{hospitals.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
    <div className="cw-ownership-field"><span>Abteilungen</span><div className="cw-ownership-checks">{visibleDepartments.map((x) => <label key={x.id} className="cw-ownership-check"><input type="checkbox" checked={departmentIds.includes(x.id)} onChange={() => toggleDepartment(x.id)} /><span>{x.name}</span></label>)}</div></div>
    <label><span>Kostenstelle</span><select value={centerId} onChange={(e) => setCenterId(e.target.value)} disabled={!hospitalId}><option value="">Keine Kostenstelle</option>{visibleCenters.map((x) => <option key={x.id} value={x.id}>{x.code} · {x.name}</option>)}</select></label>
    <label><span>Verantwortlich</span><select value={responsibleId} onChange={(e) => setResponsibleId(e.target.value)}><option value="">Nicht zugewiesen</option>{visibleAssignees.map((x) => <option key={x.id} value={x.id}>{x.display_name}</option>)}</select></label>
    <div className="cw-ownership-actions"><button type="button" className="cw-primary-action" onClick={() => void save()} disabled={saving}>{saving ? "Wird gespeichert…" : "Zuordnung speichern"}</button>{message ? <span>{message}</span> : null}</div>
  </div></section>;
}
