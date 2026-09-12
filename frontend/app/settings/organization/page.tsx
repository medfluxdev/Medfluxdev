"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

type Hospital = { id: string; name: string; code: string; address?: string | null; is_active: boolean };
type Department = { id: string; hospital_id: string; name: string; code: string; is_active: boolean };
type CostCenter = { id: string; hospital_id: string; department_id: string | null; name: string; code: string; is_active: boolean };
type Structure = { hospitals: Hospital[]; departments: Department[] };

export default function OrganizationSettingsPage() {
  const { role, organizationSlug } = useAuth();
  const [data, setData] = useState<Structure>({ hospitals: [], departments: [] });
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
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

  const load = useCallback(() => {
    if (!organizationSlug) return;
    const query = encodeURIComponent(organizationSlug);
    Promise.all([
      apiGet<Structure>(`/api/organization-structure?organization_slug=${query}`),
      apiGet<{ items: CostCenter[] }>(`/api/cost-centers?organization_slug=${query}`),
    ]).then(([structure, centers]) => {
      setData(structure);
      setCostCenters(centers.items);
      const firstHospital = structure.hospitals[0]?.id || "";
      setDepartmentHospitalId((current) => current || firstHospital);
      setCostCenterHospitalId((current) => current || firstHospital);
    }).catch(() => setMessage("Organisationsstruktur konnte nicht geladen werden."));
  }, [organizationSlug]);

  useEffect(() => { load(); }, [load]);

  const departmentsByHospital = useMemo(() => {
    const map = new Map<string, Department[]>();
    for (const department of data.departments) {
      const list = map.get(department.hospital_id) ?? [];
      list.push(department);
      map.set(department.hospital_id, list);
    }
    return map;
  }, [data.departments]);

  const costCenterDepartments = useMemo(
    () => data.departments.filter((item) => item.hospital_id === costCenterHospitalId && item.is_active),
    [data.departments, costCenterHospitalId]
  );

  async function addHospital(event: FormEvent) {
    event.preventDefault(); if (!organizationSlug) return; setMessage("");
    try {
      await apiPost(`/api/organization-structure/hospitals?organization_slug=${encodeURIComponent(organizationSlug)}`, { name: hospitalName, code: hospitalCode, address: hospitalAddress || null });
      setHospitalName(""); setHospitalCode(""); setHospitalAddress(""); setMessage("Krankenhaus wurde angelegt."); load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Krankenhaus konnte nicht angelegt werden."); }
  }

  async function addDepartment(event: FormEvent) {
    event.preventDefault(); if (!organizationSlug) return; setMessage("");
    try {
      await apiPost(`/api/organization-structure/departments?organization_slug=${encodeURIComponent(organizationSlug)}`, { hospital_id: departmentHospitalId, name: departmentName, code: departmentCode });
      setDepartmentName(""); setDepartmentCode(""); setMessage("Abteilung wurde angelegt."); load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Abteilung konnte nicht angelegt werden."); }
  }

  async function addCostCenter(event: FormEvent) {
    event.preventDefault(); if (!organizationSlug) return; setMessage("");
    try {
      await apiPost(`/api/cost-centers?organization_slug=${encodeURIComponent(organizationSlug)}`, {
        hospital_id: costCenterHospitalId,
        department_id: costCenterDepartmentId || null,
        code: costCenterCode,
        name: costCenterName,
      });
      setCostCenterCode(""); setCostCenterName(""); setMessage("Kostenstelle wurde angelegt."); load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Kostenstelle konnte nicht angelegt werden."); }
  }

  if (role !== "admin") return <div className="page"><p>Dieser Bereich ist nur für Administratoren verfügbar.</p></div>;

  return <div className="page org-settings-page">
    <div className="org-settings-head"><div><span>Administration</span><h1>Organisation</h1><p>Krankenhäuser, Abteilungen und Kostenstellen zentral verwalten.</p></div><Link href="/settings">Zurück zu Einstellungen</Link></div>
    {message ? <div className="org-settings-message">{message}</div> : null}
    <div className="org-settings-forms">
      <form onSubmit={addHospital} className="org-settings-card"><h2>Krankenhaus hinzufügen</h2><label>Name<input value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} required /></label><label>Kürzel<input value={hospitalCode} onChange={(e) => setHospitalCode(e.target.value)} placeholder="z. B. HD" required /></label><label>Adresse<input value={hospitalAddress} onChange={(e) => setHospitalAddress(e.target.value)} /></label><button type="submit">Krankenhaus anlegen</button></form>
      <form onSubmit={addDepartment} className="org-settings-card"><h2>Abteilung hinzufügen</h2><label>Krankenhaus<select value={departmentHospitalId} onChange={(e) => setDepartmentHospitalId(e.target.value)} required><option value="">Bitte wählen</option>{data.hospitals.map((hospital) => <option key={hospital.id} value={hospital.id}>{hospital.name}</option>)}</select></label><label>Name<input value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} required /></label><label>Kürzel<input value={departmentCode} onChange={(e) => setDepartmentCode(e.target.value)} placeholder="z. B. MT" required /></label><button type="submit" disabled={!departmentHospitalId}>Abteilung anlegen</button></form>
      <form onSubmit={addCostCenter} className="org-settings-card"><h2>Kostenstelle hinzufügen</h2><label>Krankenhaus<select value={costCenterHospitalId} onChange={(e) => { setCostCenterHospitalId(e.target.value); setCostCenterDepartmentId(""); }} required><option value="">Bitte wählen</option>{data.hospitals.map((hospital) => <option key={hospital.id} value={hospital.id}>{hospital.name}</option>)}</select></label><label>Abteilung<select value={costCenterDepartmentId} onChange={(e) => setCostCenterDepartmentId(e.target.value)} disabled={!costCenterHospitalId}><option value="">Krankenhausweit</option>{costCenterDepartments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select></label><label>Kostenstelle<input value={costCenterCode} onChange={(e) => setCostCenterCode(e.target.value)} placeholder="z. B. 4711" required /></label><label>Bezeichnung<input value={costCenterName} onChange={(e) => setCostCenterName(e.target.value)} required /></label><button type="submit" disabled={!costCenterHospitalId}>Kostenstelle anlegen</button></form>
    </div>
    <section className="org-settings-list">
      <div className="org-settings-list-head"><h2>Struktur</h2><span>{data.hospitals.length} Krankenhäuser · {data.departments.length} Abteilungen · {costCenters.length} Kostenstellen</span></div>
      {data.hospitals.length === 0 ? <p>Noch keine Krankenhäuser angelegt.</p> : data.hospitals.map((hospital) => <article key={hospital.id} className="org-hospital-row"><div className="org-hospital-title"><strong>{hospital.name}</strong><span>{hospital.code}</span>{hospital.address ? <small>{hospital.address}</small> : null}</div><div className="org-department-chips">{(departmentsByHospital.get(hospital.id) ?? []).map((department) => <span key={department.id}>{department.name} <small>{department.code}</small></span>)}{(departmentsByHospital.get(hospital.id) ?? []).length === 0 ? <em>Keine Abteilungen</em> : null}</div><div className="org-department-chips">{costCenters.filter((center) => center.hospital_id === hospital.id).map((center) => <span key={center.id}>{center.code} <small>{center.name}</small></span>)}</div></article>)}
    </section>
  </div>;
}
