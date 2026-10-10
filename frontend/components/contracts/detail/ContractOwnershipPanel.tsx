"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { getOrganizationStructure, listCostCenters } from "@/lib/domain-api/organizations";
import { departmentFullPath } from "@/lib/organization-tree";
import {
  getContractDepartmentRoles,
  getContractOwnership,
  listOwnershipAssignees,
  updateContractDepartmentRoles,
  updateContractOwnership,
  type ContractDepartmentRolesDto,
  type ContractOwnershipDto,
} from "@/lib/domain-api/ownership";

type Item = { id: string; name: string; code: string; is_active: boolean };
type Department = Item & { hospital_id: string; parent_id?: string | null };
type Center = Item & { hospital_id: string; department_id: string | null };
type Assignee = { id: string; display_name: string; role: string; hospital_id: string | null; department_id: string | null };

export default function ContractOwnershipPanel({ contractId, orgSlug, onSaved }: { contractId: string; orgSlug: string; onSaved?: () => void }) {
  const { role, account } = useAuth();
  const editable = Boolean(account?.is_developer || role === "admin" || role === "contract_manager");
  const [hospitals, setHospitals] = useState<Item[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [assignees, setAssignees] = useState<Assignee[]>([]);
  const [assignment, setAssignment] = useState<ContractOwnershipDto | null>(null);
  const [roles, setRoles] = useState<ContractDepartmentRolesDto | null>(null);
  const [hospitalId, setHospitalId] = useState("");
  const [responsibleDepartmentId, setResponsibleDepartmentId] = useState("");
  const [beneficiaryDepartmentIds, setBeneficiaryDepartmentIds] = useState<string[]>([]);
  const [centerId, setCenterId] = useState("");
  const [responsibleId, setResponsibleId] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!editable) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getOrganizationStructure(orgSlug),
      listCostCenters(orgSlug),
      listOwnershipAssignees(orgSlug),
      getContractOwnership(orgSlug, contractId),
      getContractDepartmentRoles(orgSlug, contractId),
    ]).then(([structure, costCenters, users, ownership, departmentRoles]) => {
      if (cancelled) return;
      const activeDepartments = (structure.departments ?? []).filter((item) => item.is_active);
      setHospitals((structure.hospitals ?? []).filter((item) => item.is_active));
      setDepartments(activeDepartments);
      setCenters((costCenters.items ?? []).filter((item) => item.is_active));
      setAssignees(users.items ?? []);
      setAssignment(ownership);
      setRoles({
        ...departmentRoles,
        responsible_department_id: departmentRoles.responsible_department_id ?? null,
        beneficiary_department_ids: departmentRoles.beneficiary_department_ids ?? [],
        unclassified_department_ids: departmentRoles.unclassified_department_ids ?? [],
      });
      setHospitalId(ownership.hospital_id ?? "");
      setResponsibleDepartmentId(departmentRoles.responsible_department_id ?? "");
      setBeneficiaryDepartmentIds(departmentRoles.beneficiary_department_ids ?? []);
      setCenterId(ownership.cost_center_id ?? "");
      setResponsibleId(ownership.responsible_account_id ?? "");
    }).catch(() => { if (!cancelled) setMessage("Zuordnung konnte nicht geladen werden."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [contractId, editable, orgSlug]);

  const visibleDepartments = useMemo(
    () => departments.filter((item) => item.hospital_id === hospitalId),
    [departments, hospitalId],
  );
  const selectedDepartments = useMemo(
    () => new Set([responsibleDepartmentId, ...beneficiaryDepartmentIds].filter(Boolean)),
    [responsibleDepartmentId, beneficiaryDepartmentIds],
  );
  const visibleCenters = useMemo(() => centers.filter((item) =>
    item.hospital_id === hospitalId && (!item.department_id || selectedDepartments.has(item.department_id))),
  [centers, hospitalId, selectedDepartments]);
  const visibleAssignees = useMemo(() => assignees.filter((item) =>
    (!item.hospital_id || item.hospital_id === hospitalId) &&
    (!item.department_id || selectedDepartments.size === 0 || selectedDepartments.has(item.department_id))),
  [assignees, hospitalId, selectedDepartments]);
  const hospitalLocked = Boolean(roles?.responsible_department_id || roles?.beneficiary_department_ids.length);

  function toggleBeneficiary(id: string) {
    if (id === responsibleDepartmentId) return;
    setBeneficiaryDepartmentIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
    setCenterId("");
  }

  async function save() {
    if (!assignment) return;
    if (responsibleDepartmentId && !hospitalId) {
      setMessage("Wählen Sie zuerst ein Krankenhaus aus.");
      return;
    }
    if (!responsibleDepartmentId && beneficiaryDepartmentIds.length) {
      setMessage("Wählen Sie einen verantwortlichen Bereich aus, bevor nutzende Bereiche gespeichert werden.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const existingDepartmentIds = assignment.hospital_id === hospitalId ? assignment.department_ids : [];
      const ownership = await updateContractOwnership(orgSlug, contractId, {
        hospital_id: hospitalId || null,
        department_ids: existingDepartmentIds,
        cost_center_id: centerId || null,
        responsible_account_id: responsibleId || null,
      });
      if (hospitalId && responsibleDepartmentId) {
        await updateContractDepartmentRoles(orgSlug, contractId, {
          responsible_department_id: responsibleDepartmentId,
          beneficiary_department_ids: beneficiaryDepartmentIds.filter((id) => id !== responsibleDepartmentId),
        });
      } else if (!hospitalId && roles && (roles.responsible_department_id || roles.beneficiary_department_ids.length)) {
        throw new Error("Entfernen Sie zuerst die Bereichsrollen, bevor Sie das Krankenhaus aufheben.");
      }
      setAssignment(ownership);
      setMessage("Organisationszuordnung gespeichert.");
      onSaved?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Zuordnung konnte nicht gespeichert werden.");
    } finally {
      setSaving(false);
    }
  }

  if (!editable) return null;
  return <section className="cw-section cw-ownership-section" aria-labelledby="cw-ownership-heading">
    <div className="cw-section-head"><div><h2 id="cw-ownership-heading">Organisationszuordnung</h2><p>Verantwortlichen Bereich, nutzende Bereiche und zuständige Person getrennt festlegen.</p></div></div>
    {loading ? <p role="status">Zuordnung wird geladen…</p> : <div className="cw-ownership-grid">
      <label><span>Krankenhaus</span><select value={hospitalId} disabled={hospitalLocked} onChange={(event) => {
        setHospitalId(event.target.value);
        setResponsibleDepartmentId("");
        setBeneficiaryDepartmentIds([]);
        setCenterId("");
      }}><option value="">Organisationsweit</option>{hospitals.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{hospitalLocked ? <small>Das Krankenhaus lässt sich erst nach Aufheben der Bereichsrollen ändern.</small> : null}</label>
      <label><span>Verantwortliche Abteilung</span><select value={responsibleDepartmentId} disabled={!hospitalId} onChange={(event) => {
        const next = event.target.value;
        setResponsibleDepartmentId(next);
        setBeneficiaryDepartmentIds((current) => current.filter((id) => id !== next));
        setCenterId("");
      }}><option value="">Bitte auswählen</option>{visibleDepartments.map((item) => <option key={item.id} value={item.id}>{departmentFullPath(item, departments)}</option>)}</select></label>
      <div className="cw-ownership-field"><span>Nutzende Abteilungen</span><div className="cw-ownership-checks">{visibleDepartments.filter((item) => item.id !== responsibleDepartmentId).map((item) => <label key={item.id} className="cw-ownership-check"><input type="checkbox" checked={beneficiaryDepartmentIds.includes(item.id)} onChange={() => toggleBeneficiary(item.id)} /><span>{departmentFullPath(item, departments)}</span></label>)}{hospitalId && visibleDepartments.length === 0 ? <small>Für dieses Krankenhaus sind keine aktiven Abteilungen vorhanden.</small> : null}</div></div>
      <label><span>Kostenstelle</span><select value={centerId} onChange={(event) => setCenterId(event.target.value)} disabled={!hospitalId}><option value="">Keine Kostenstelle</option>{visibleCenters.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}{item.department_id ? ` — ${departmentFullPath(departments.find((department) => department.id === item.department_id)!, departments)}` : " — krankenhausweit"}</option>)}</select></label>
      <label><span>Verantwortliche Person</span><select value={responsibleId} onChange={(event) => setResponsibleId(event.target.value)}><option value="">Nicht zugewiesen</option>{visibleAssignees.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
      {roles?.unclassified_department_ids.length ? <p className="cw-ownership-note" role="note">Historische Zuordnung ohne dokumentierte Rolle: {roles.unclassified_department_ids.map((id) => {
        const department = departments.find((item) => item.id === id);
        return department ? departmentFullPath(department, departments) : "Unbekannter Bereich";
      }).join(" · ")}. Sie wird nicht automatisch als verantwortlich oder nutzend eingestuft.</p> : null}
      <div className="cw-ownership-actions"><button type="button" className="cw-primary-action" onClick={() => void save()} disabled={saving || loading}>{saving ? "Wird gespeichert…" : "Zuordnung speichern"}</button>{message ? <span role="status">{message}</span> : null}</div>
    </div>}
  </section>;
}
