"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

type Hospital = { id: string; name: string; code: string; is_active: boolean };
type Department = { id: string; hospital_id: string; name: string; code: string; is_active: boolean };
type Structure = { hospitals: Hospital[]; departments: Department[] };

export default function OrganizationScopePicker() {
  const [structure, setStructure] = useState<Structure>({ hospitals: [], departments: [] });
  const [hospitalId, setHospitalId] = useState("");
  const [departmentId, setDepartmentId] = useState("");

  useEffect(() => {
    setHospitalId(localStorage.getItem("medflux.hospitalId") ?? "");
    setDepartmentId(localStorage.getItem("medflux.departmentId") ?? "");
    apiGet<Structure>(`/api/organization-structure?organization_slug=${encodeURIComponent(ORG_SLUG)}`)
      .then(setStructure)
      .catch(() => setStructure({ hospitals: [], departments: [] }));
  }, []);

  const departments = useMemo(
    () => structure.departments.filter((item) => item.is_active && (!hospitalId || item.hospital_id === hospitalId)),
    [structure.departments, hospitalId]
  );

  function chooseHospital(value: string) {
    setHospitalId(value);
    setDepartmentId("");
    if (value) localStorage.setItem("medflux.hospitalId", value); else localStorage.removeItem("medflux.hospitalId");
    localStorage.removeItem("medflux.departmentId");
    window.dispatchEvent(new CustomEvent("medflux:scope-change", { detail: { hospitalId: value, departmentId: "" } }));
  }

  function chooseDepartment(value: string) {
    setDepartmentId(value);
    if (value) localStorage.setItem("medflux.departmentId", value); else localStorage.removeItem("medflux.departmentId");
    window.dispatchEvent(new CustomEvent("medflux:scope-change", { detail: { hospitalId, departmentId: value } }));
  }

  if (structure.hospitals.length === 0) return null;

  return (
    <div className="scope-picker" aria-label="Krankenhaus und Abteilung auswählen">
      <select value={hospitalId} onChange={(event) => chooseHospital(event.target.value)} aria-label="Krankenhaus">
        <option value="">Alle Krankenhäuser</option>
        {structure.hospitals.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      <select value={departmentId} onChange={(event) => chooseDepartment(event.target.value)} aria-label="Abteilung" disabled={!hospitalId}>
        <option value="">Alle Abteilungen</option>
        {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </div>
  );
}
