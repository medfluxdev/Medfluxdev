"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  createCostCenter,
  createDepartment,
  createHospital,
  getOrganizationStructure,
  listCostCenters,
  updateDepartment,
  updateHospital,
  type CostCenterDto,
  type DepartmentDto,
  type HospitalDto,
  type OrganizationStructureDto,
} from "@/lib/domain-api/organizations";

export default function OrganizationStructureManager({ organizationSlug }: { organizationSlug: string }) {
  const [data, setData] = useState<OrganizationStructureDto>({ hospitals: [], departments: [] });
  const [costCenters, setCostCenters] = useState<CostCenterDto[]>([]);
  const [hospitalName, setHospitalName] = useState("");
  const [hospitalCode, setHospitalCode] = useState("");
  const [hospitalAddress, setHospitalAddress] = useState("");
  const [departmentHospitalId, setDepartmentHospitalId] = useState("");
  const [departmentName, setDepartmentName] = useState("");
  const [departmentCode, setDepartmentCode] = useState("");
  const [costCenterHospitalId, setCostCenterHospitalId] = useState("");
  const [costCenterDepartmentId, setCostCenterDepartmentId] = useState("");
  const [costCenterCode, setCostCenterCode] = useState("");
  const [costCenterName, setCostCenterName] = useState("");
  const [message, setMessage] = useState("");

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

  const departmentsByHospital = useMemo(() => {
    const map = new Map<string, DepartmentDto[]>();
    for (const department of data.departments) {
      const list = map.get(department.hospital_id) ?? [];
      list.push(department);
      map.set(department.hospital_id, list);
    }
    return map;
  }, [data.departments]);

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
      await createDepartment(organizationSlug, { hospital_id: departmentHospitalId, name: departmentName, code: departmentCode });
      setDepartmentName(""); setDepartmentCode("");
      setMessage("Abteilung wurde angelegt.");
      await load();
    } catch (err) { setMessage(err instanceof Error ? err.message : "Abteilung konnte nicht angelegt werden."); }
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
    const name = window.prompt("Name der Abteilung", row.name);
    if (!name || name === row.name) return;
    try { await updateDepartment(organizationSlug, row.id, { name }); setMessage("Abteilung wurde aktualisiert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Abteilung konnte nicht aktualisiert werden."); }
  }

  async function toggleDepartment(row: DepartmentDto) {
    try { await updateDepartment(organizationSlug, row.id, { is_active: !row.is_active }); setMessage(row.is_active ? "Abteilung wurde deaktiviert." : "Abteilung wurde aktiviert."); await load(); }
    catch (err) { setMessage(err instanceof Error ? err.message : "Status konnte nicht geändert werden."); }
  }

  return <>
    {message ? <div className="org-settings-message" role="status">{message}</div> : null}
    <div className="org-settings-forms">
      <form onSubmit={submitHospital} className="org-settings-card"><h2>Krankenhaus hinzufügen</h2><label>Name<input value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} required /></label><label>Kürzel<input value={hospitalCode} onChange={(e) => setHospitalCode(e.target.value)} required /></label><label>Adresse<input value={hospitalAddress} onChange={(e) => setHospitalAddress(e.target.value)} /></label><button type="submit">Krankenhaus anlegen</button></form>
      <form onSubmit={submitDepartment} className="org-settings-card"><h2>Abteilung hinzufügen</h2><label>Krankenhaus<select value={departmentHospitalId} onChange={(e) => setDepartmentHospitalId(e.target.value)} required><option value="">Bitte wählen</option>{data.hospitals.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Name<input value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} required /></label><label>Kürzel<input value={departmentCode} onChange={(e) => setDepartmentCode(e.target.value)} required /></label><button type="submit" disabled={!departmentHospitalId}>Abteilung anlegen</button></form>
      <form onSubmit={submitCostCenter} className="org-settings-card"><h2>Kostenstelle hinzufügen</h2><label>Krankenhaus<select value={costCenterHospitalId} onChange={(e) => { setCostCenterHospitalId(e.target.value); setCostCenterDepartmentId(""); }} required><option value="">Bitte wählen</option>{data.hospitals.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Abteilung<select value={costCenterDepartmentId} onChange={(e) => setCostCenterDepartmentId(e.target.value)} disabled={!costCenterHospitalId}><option value="">Krankenhausweit</option>{costCenterDepartments.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Kostenstelle<input value={costCenterCode} onChange={(e) => setCostCenterCode(e.target.value)} required /></label><label>Bezeichnung<input value={costCenterName} onChange={(e) => setCostCenterName(e.target.value)} required /></label><button type="submit" disabled={!costCenterHospitalId}>Kostenstelle anlegen</button></form>
    </div>
    <section className="org-settings-list">
      <div className="org-settings-list-head"><h2>Struktur</h2><span>{data.hospitals.length} Krankenhäuser · {data.departments.length} Abteilungen · {costCenters.length} Kostenstellen</span></div>
      {data.hospitals.length === 0 ? <p>Noch keine Krankenhäuser angelegt.</p> : data.hospitals.map((hospital) => <article key={hospital.id} className={`org-hospital-row${hospital.is_active ? "" : " inactive"}`}>
        <div className="org-hospital-title"><strong>{hospital.name}</strong><span>{hospital.code}</span>{hospital.address ? <small>{hospital.address}</small> : null}<small>{hospital.is_active ? "Aktiv" : "Inaktiv"}</small></div>
        <div className="org-department-chips">{(departmentsByHospital.get(hospital.id) ?? []).map((department) => <span key={department.id}>{department.name} <small>{department.code} · {department.is_active ? "Aktiv" : "Inaktiv"}</small><button type="button" onClick={() => void renameDepartment(department)}>Bearbeiten</button><button type="button" onClick={() => void toggleDepartment(department)}>{department.is_active ? "Deaktivieren" : "Aktivieren"}</button></span>)}{(departmentsByHospital.get(hospital.id) ?? []).length === 0 ? <em>Keine Abteilungen</em> : null}</div>
        <div className="org-department-chips">{costCenters.filter((center) => center.hospital_id === hospital.id).map((center) => <span key={center.id}>{center.code} <small>{center.name}</small></span>)}</div>
        <div className="account-card-actions"><button type="button" onClick={() => void renameHospital(hospital)}>Bearbeiten</button><button type="button" onClick={() => void toggleHospital(hospital)}>{hospital.is_active ? "Deaktivieren" : "Aktivieren"}</button></div>
      </article>)}
    </section>
  </>;
}
