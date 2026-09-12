"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";

type Hospital = { id: string; name: string; code: string; is_active: boolean };
type Department = { id: string; hospital_id: string; name: string; code: string; is_active: boolean };
type Structure = { hospitals: Hospital[]; departments: Department[] };

export default function OrganizationScopePicker() {
  const { membership, memberships, organizationSlug, role, selectOrganization } = useAuth();
  const [structure, setStructure] = useState<Structure>({ hospitals: [], departments: [] });
  const [hospitalId, setHospitalId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const isAdmin = role === "admin";

  useEffect(() => {
    if (!organizationSlug || !membership) return;
    const assignedHospital = membership.hospital_id ?? "";
    const assignedDepartment = membership.department_id ?? "";
    const initialHospital = isAdmin ? (localStorage.getItem("medflux.hospitalId") ?? assignedHospital) : assignedHospital;
    const initialDepartment = isAdmin ? (localStorage.getItem("medflux.departmentId") ?? assignedDepartment) : assignedDepartment;
    setHospitalId(initialHospital);
    setDepartmentId(initialDepartment);
    if (!isAdmin) {
      if (assignedHospital) localStorage.setItem("medflux.hospitalId", assignedHospital); else localStorage.removeItem("medflux.hospitalId");
      if (assignedDepartment) localStorage.setItem("medflux.departmentId", assignedDepartment); else localStorage.removeItem("medflux.departmentId");
    }
    apiGet<Structure>(`/api/organization-structure?organization_slug=${encodeURIComponent(organizationSlug)}`)
      .then(setStructure)
      .catch(() => setStructure({ hospitals: [], departments: [] }));
  }, [organizationSlug, membership, isAdmin]);

  const departments = useMemo(() => structure.departments.filter((item) => item.is_active && (!hospitalId || item.hospital_id === hospitalId)), [structure.departments, hospitalId]);

  function changeOrganization(slug: string) {
    selectOrganization(slug);
    localStorage.removeItem("medflux.hospitalId");
    localStorage.removeItem("medflux.departmentId");
    window.location.assign("/");
  }

  function chooseHospital(value: string) {
    if (!isAdmin) return;
    setHospitalId(value); setDepartmentId("");
    if (value) localStorage.setItem("medflux.hospitalId", value); else localStorage.removeItem("medflux.hospitalId");
    localStorage.removeItem("medflux.departmentId");
    window.dispatchEvent(new CustomEvent("medflux:scope-change", { detail: { hospitalId: value, departmentId: "" } }));
  }

  function chooseDepartment(value: string) {
    if (!isAdmin) return;
    setDepartmentId(value);
    if (value) localStorage.setItem("medflux.departmentId", value); else localStorage.removeItem("medflux.departmentId");
    window.dispatchEvent(new CustomEvent("medflux:scope-change", { detail: { hospitalId, departmentId: value } }));
  }

  if (!membership) return null;

  return <div className="scope-picker" aria-label="Arbeitsbereich auswählen">
    {isAdmin && memberships.length > 1 ? <select value={organizationSlug ?? ""} onChange={(event) => changeOrganization(event.target.value)} aria-label="Organisation">{memberships.filter((item) => item.role === "admin").map((item) => <option key={item.organization_id} value={item.organization_slug}>{item.organization_name}</option>)}</select> : null}
    {structure.hospitals.length > 0 ? <select value={hospitalId} onChange={(event) => chooseHospital(event.target.value)} aria-label="Krankenhaus" disabled={!isAdmin}>
      {isAdmin ? <option value="">Alle Krankenhäuser</option> : null}
      {structure.hospitals.filter((item) => item.is_active && (isAdmin || item.id === membership.hospital_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select> : null}
    {hospitalId && structure.departments.length > 0 ? <select value={departmentId} onChange={(event) => chooseDepartment(event.target.value)} aria-label="Abteilung" disabled={!isAdmin}>
      {isAdmin || !membership.department_id ? <option value="">Alle Abteilungen</option> : null}
      {departments.filter((item) => isAdmin || !membership.department_id || item.id === membership.department_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select> : null}
  </div>;
}
