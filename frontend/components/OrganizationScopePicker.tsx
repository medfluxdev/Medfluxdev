"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { getOrganizationStructure, type OrganizationStructureDto } from "@/lib/domain-api/organizations";

const EMPTY_STRUCTURE: OrganizationStructureDto = { hospitals: [], departments: [] };

function requestScopeChange(detail: Record<string, string>): boolean {
  return window.dispatchEvent(new CustomEvent("medflux:scope-change", { detail, cancelable: true }));
}

export default function OrganizationScopePicker() {
  const { membership, memberships, organizationSlug, role, selectOrganization } = useAuth();
  const [structure, setStructure] = useState<OrganizationStructureDto>(EMPTY_STRUCTURE);
  const [hospitalId, setHospitalId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const isAdmin = role === "admin";
  const availableMemberships = memberships ?? [];

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
    let active = true;
    getOrganizationStructure(organizationSlug)
      .then((value) => {
        if (!active) return;
        setStructure({ hospitals: value?.hospitals ?? [], departments: value?.departments ?? [] });
      })
      .catch(() => { if (active) setStructure(EMPTY_STRUCTURE); });
    return () => { active = false; };
  }, [organizationSlug, membership, isAdmin]);

  const departments = useMemo(
    () => (structure.departments ?? []).filter((item) => item.is_active && (!hospitalId || item.hospital_id === hospitalId)),
    [structure.departments, hospitalId]
  );

  function changeOrganization(slug: string) {
    if (!requestScopeChange({ organizationSlug: slug, hospitalId: "", departmentId: "" })) return;
    selectOrganization(slug);
    localStorage.removeItem("medflux.hospitalId");
    localStorage.removeItem("medflux.departmentId");
    window.location.assign("/");
  }

  function chooseHospital(value: string) {
    if (!isAdmin) return;
    if (!requestScopeChange({ hospitalId: value, departmentId: "" })) return;
    if (value) localStorage.setItem("medflux.hospitalId", value); else localStorage.removeItem("medflux.hospitalId");
    localStorage.removeItem("medflux.departmentId");
    setHospitalId(value);
    setDepartmentId("");
    window.location.reload();
  }

  function chooseDepartment(value: string) {
    if (!isAdmin) return;
    if (!requestScopeChange({ hospitalId, departmentId: value })) return;
    if (value) localStorage.setItem("medflux.departmentId", value); else localStorage.removeItem("medflux.departmentId");
    setDepartmentId(value);
    window.location.reload();
  }

  if (!membership) return null;
  const hospitals = structure.hospitals ?? [];
  const allDepartments = structure.departments ?? [];

  return <div className="scope-picker" role="group" aria-label="Arbeitsbereich auswählen">
    {isAdmin && availableMemberships.length > 1 ? <select value={organizationSlug ?? ""} onChange={(event) => changeOrganization(event.target.value)} aria-label="Organisation">{availableMemberships.filter((item) => item.role === "admin").map((item) => <option key={item.organization_id} value={item.organization_slug}>{item.organization_name}</option>)}</select> : null}
    {hospitals.length > 0 ? <select value={hospitalId} onChange={(event) => chooseHospital(event.target.value)} aria-label="Krankenhaus" disabled={!isAdmin}>
      {isAdmin ? <option value="">Alle Krankenhäuser</option> : null}
      {hospitals.filter((item) => item.is_active && (isAdmin || item.id === membership.hospital_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select> : null}
    {hospitalId && allDepartments.length > 0 ? <select value={departmentId} onChange={(event) => chooseDepartment(event.target.value)} aria-label="Abteilung" disabled={!isAdmin}>
      {isAdmin || !membership.department_id ? <option value="">Alle Abteilungen</option> : null}
      {departments.filter((item) => isAdmin || !membership.department_id || item.id === membership.department_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select> : null}
  </div>;
}
