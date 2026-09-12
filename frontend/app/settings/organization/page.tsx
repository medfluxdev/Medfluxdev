"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import { ORG_SLUG } from "@/components/ClientNav";

type Hospital = { id: string; name: string; code: string; address?: string | null; is_active: boolean };
type Department = { id: string; hospital_id: string; name: string; code: string; is_active: boolean };
type Structure = { hospitals: Hospital[]; departments: Department[] };

export default function OrganizationSettingsPage() {
  const { role } = useAuth();
  const [data, setData] = useState<Structure>({ hospitals: [], departments: [] });
  const [hospitalName, setHospitalName] = useState("");
  const [hospitalCode, setHospitalCode] = useState("");
  const [hospitalAddress, setHospitalAddress] = useState("");
  const [departmentHospitalId, setDepartmentHospitalId] = useState("");
  const [departmentName, setDepartmentName] = useState("");
  const [departmentCode, setDepartmentCode] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(() => {
    apiGet<Structure>(`/api/organization-structure?organization_slug=${encodeURIComponent(ORG_SLUG)}`)
      .then((result) => {
        setData(result);
        setDepartmentHospitalId((current) => current || result.hospitals[0]?.id || "");
      })
      .catch(() => setMessage("Organisationsstruktur konnte nicht geladen werden."));
  }, []);

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

  async function addHospital(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      await apiPost(`/api/organization-structure/hospitals?organization_slug=${encodeURIComponent(ORG_SLUG)}`, {
        name: hospitalName,
        code: hospitalCode,
        address: hospitalAddress || null,
      });
      setHospitalName(""); setHospitalCode(""); setHospitalAddress("");
      setMessage("Krankenhaus wurde angelegt.");
      load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Krankenhaus konnte nicht angelegt werden.");
    }
  }

  async function addDepartment(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      await apiPost(`/api/organization-structure/departments?organization_slug=${encodeURIComponent(ORG_SLUG)}`, {
        hospital_id: departmentHospitalId,
        name: departmentName,
        code: departmentCode,
      });
      setDepartmentName(""); setDepartmentCode("");
      setMessage("Abteilung wurde angelegt.");
      load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Abteilung konnte nicht angelegt werden.");
    }
  }

  if (role !== "admin") return <div className="page"><p>Dieser Bereich ist nur für Administratoren verfügbar.</p></div>;

  return (
    <div className="page org-settings-page">
      <div className="org-settings-head">
        <div><span>Administration</span><h1>Organisation</h1><p>Krankenhäuser und Abteilungen zentral verwalten.</p></div>
        <Link href="/settings">Zurück zu Einstellungen</Link>
      </div>

      {message ? <div className="org-settings-message">{message}</div> : null}

      <div className="org-settings-forms">
        <form onSubmit={addHospital} className="org-settings-card">
          <h2>Krankenhaus hinzufügen</h2>
          <label>Name<input value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} required /></label>
          <label>Kürzel<input value={hospitalCode} onChange={(e) => setHospitalCode(e.target.value)} placeholder="z. B. HD" required /></label>
          <label>Adresse<input value={hospitalAddress} onChange={(e) => setHospitalAddress(e.target.value)} /></label>
          <button type="submit">Krankenhaus anlegen</button>
        </form>

        <form onSubmit={addDepartment} className="org-settings-card">
          <h2>Abteilung hinzufügen</h2>
          <label>Krankenhaus<select value={departmentHospitalId} onChange={(e) => setDepartmentHospitalId(e.target.value)} required><option value="">Bitte wählen</option>{data.hospitals.map((hospital) => <option key={hospital.id} value={hospital.id}>{hospital.name}</option>)}</select></label>
          <label>Name<input value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} required /></label>
          <label>Kürzel<input value={departmentCode} onChange={(e) => setDepartmentCode(e.target.value)} placeholder="z. B. MT" required /></label>
          <button type="submit" disabled={!departmentHospitalId}>Abteilung anlegen</button>
        </form>
      </div>

      <section className="org-settings-list">
        <div className="org-settings-list-head"><h2>Struktur</h2><span>{data.hospitals.length} Krankenhäuser · {data.departments.length} Abteilungen</span></div>
        {data.hospitals.length === 0 ? <p>Noch keine Krankenhäuser angelegt.</p> : data.hospitals.map((hospital) => (
          <article key={hospital.id} className="org-hospital-row">
            <div className="org-hospital-title"><strong>{hospital.name}</strong><span>{hospital.code}</span>{hospital.address ? <small>{hospital.address}</small> : null}</div>
            <div className="org-department-chips">
              {(departmentsByHospital.get(hospital.id) ?? []).map((department) => <span key={department.id}>{department.name} <small>{department.code}</small></span>)}
              {(departmentsByHospital.get(hospital.id) ?? []).length === 0 ? <em>Keine Abteilungen</em> : null}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
