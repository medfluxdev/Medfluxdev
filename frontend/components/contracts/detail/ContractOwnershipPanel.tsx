"use client";

import Link from "next/link";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { getOrganizationStructure, listCostCenters } from "@/lib/domain-api/organizations";
import { listContractTypes, type ContractCategoryDto, type ContractTypeDto } from "@/lib/domain-api/catalogs";
import { getContractRegister, updateContractRegister } from "@/lib/domain-api/register";
import { departmentFullPath } from "@/lib/organization-tree";
import { contractHref } from "@/lib/fix-targets";
import { deviceTypeGroups } from "@/lib/device-type-match";
import {
  getContractDeviceTypes,
  listDeviceTypes,
  saveContractDeviceTypes,
  type ContractDeviceTypeDto,
  type DeviceTypeDto,
} from "@/lib/domain-api/deviceTypes";
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
  const [furtherIds, setFurtherIds] = useState<string[]>([]);
  // Vertragstyp wird in den Vertragsdaten gespeichert; hier nur mit erfasst, weil er zur Zuordnung gehört.
  const [types, setTypes] = useState<ContractTypeDto[]>([]);
  const [categories, setCategories] = useState<ContractCategoryDto[]>([]);
  const [typeId, setTypeId] = useState("");
  const [savedTypeId, setSavedTypeId] = useState("");
  const [savedCategoryId, setSavedCategoryId] = useState("");
  // Gerätearten des Vertrags (Anzahl und Notiz bleiben erhalten; gepflegt unter Verknüpfungen → Geräte).
  const [deviceCatalog, setDeviceCatalog] = useState<DeviceTypeDto[] | null>(null);
  const [savedDevices, setSavedDevices] = useState<ContractDeviceTypeDto[]>([]);
  const [deviceIds, setDeviceIds] = useState<string[]>([]);
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
      listContractTypes(orgSlug).catch(() => null),
      getContractRegister(orgSlug, contractId).catch(() => null),
      listDeviceTypes(orgSlug).catch(() => null),
      getContractDeviceTypes(orgSlug, contractId).catch(() => null),
    ]).then(([structure, costCenters, users, ownership, departmentRoles, catalog, register, deviceTypes, contractDevices]) => {
      if (cancelled) return;
      const devices = Array.isArray(contractDevices?.items) ? contractDevices.items : null;
      setDeviceCatalog(Array.isArray(deviceTypes?.items) && devices ? deviceTypes.items : null);
      setSavedDevices(devices ?? []);
      setDeviceIds((devices ?? []).map((item) => item.device_type_id));
      const currentType = (register?.fields.contract_type_id?.value as string | null | undefined) ?? "";
      setTypes((catalog?.contract_types ?? []).filter((item) => item.is_active || item.id === currentType));
      setCategories(catalog?.contract_categories ?? []);
      setTypeId(currentType);
      setSavedTypeId(currentType);
      setSavedCategoryId((register?.fields.contract_category_id?.value as string | null | undefined) ?? "");
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
      setFurtherIds(ownership.further_responsible_account_ids ?? []);
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
  // Alle Kostenstellen des Krankenhauses (passende zuerst); die Wahl einer Kostenstelle setzt ihre Abteilung.
  const visibleCenters = useMemo(() => centers
    .filter((item) => item.hospital_id === hospitalId)
    .sort((a, b) => Number(Boolean(b.department_id && selectedDepartments.has(b.department_id))) - Number(Boolean(a.department_id && selectedDepartments.has(a.department_id)))),
  [centers, hospitalId, selectedDepartments]);
  // Kostenstellen gruppiert: verantwortliche Abteilung, nutzende Abteilungen, übrige des Krankenhauses.
  const centerGroups = useMemo(() => {
    const own = visibleCenters.filter((item) => item.department_id && item.department_id === responsibleDepartmentId);
    const using = visibleCenters.filter((item) => item.department_id && beneficiaryDepartmentIds.includes(item.department_id));
    const rest = visibleCenters.filter((item) => !own.includes(item) && !using.includes(item));
    return [
      { label: "Verantwortliche Abteilung", items: own },
      { label: "Nutzende Abteilungen", items: using },
      { label: own.length || using.length ? "Weitere Kostenstellen des Krankenhauses" : "Kostenstellen des Krankenhauses", items: rest },
    ];
  }, [visibleCenters, responsibleDepartmentId, beneficiaryDepartmentIds]);
  const visibleAssignees = useMemo(() => assignees.filter((item) =>
    (!item.hospital_id || item.hospital_id === hospitalId) &&
    (!item.department_id || selectedDepartments.size === 0 || selectedDepartments.has(item.department_id))),
  [assignees, hospitalId, selectedDepartments]);
  // Alle Benutzer der Organisation; passende (Krankenhaus/Bereich) zuerst.
  const otherAssignees = useMemo(() => assignees.filter((item) => !visibleAssignees.includes(item)), [assignees, visibleAssignees]);
  const deviceGroups = useMemo(() => deviceCatalog ? deviceTypeGroups(
    deviceCatalog,
    deviceIds,
    departments.filter((item) => selectedDepartments.has(item.id)).map((item) => ({ id: item.id, path: departmentFullPath(item, departments) })),
  ) : [], [deviceCatalog, deviceIds, departments, selectedDepartments]);
  function deviceLabel(id: string) {
    return deviceCatalog?.find((item) => item.id === id)?.label ?? savedDevices.find((item) => item.device_type_id === id)?.label ?? "Geräteart";
  }
  const isAdmin = Boolean(account?.is_developer || role === "admin");
  function assigneeName(id: string) {
    return assignees.find((item) => item.id === id)?.display_name ?? "Unbekannte Person";
  }
  function personOptions(matching: Assignee[], others: Assignee[], exclude: Set<string>) {
    const first = matching.filter((item) => !exclude.has(item.id));
    const rest = others.filter((item) => !exclude.has(item.id));
    const render = (list: Assignee[]) => list.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>);
    if (!rest.length) return render(first);
    if (!first.length) return render(rest);
    return <><optgroup label="Passend zur Zuordnung">{render(first)}</optgroup><optgroup label="Weitere Benutzer der Organisation">{render(rest)}</optgroup></>;
  }
  const hospitalLocked = Boolean(roles?.responsible_department_id || roles?.beneficiary_department_ids.length);

  function toggleBeneficiary(id: string) {
    if (id === responsibleDepartmentId) return;
    setBeneficiaryDepartmentIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
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
        further_responsible_account_ids: furtherIds.filter((id) => id !== responsibleId),
      });
      if (hospitalId && responsibleDepartmentId) {
        await updateContractDepartmentRoles(orgSlug, contractId, {
          responsible_department_id: responsibleDepartmentId,
          beneficiary_department_ids: beneficiaryDepartmentIds.filter((id) => id !== responsibleDepartmentId),
        });
      } else if (!hospitalId && roles && (roles.responsible_department_id || roles.beneficiary_department_ids.length)) {
        throw new Error("Entfernen Sie zuerst die Bereichsrollen, bevor Sie das Krankenhaus aufheben.");
      }
      if (typeId !== savedTypeId) {
        // Kategorie bleibt nur, wenn sie zum neuen Typ passt (wie in den Vertragsdaten).
        const category = categories.find((item) => item.id === savedCategoryId);
        const keepCategory = Boolean(category && typeId && category.contract_type_ids.includes(typeId));
        await updateContractRegister(orgSlug, contractId, { changes: { contract_type_id: typeId || null, ...(keepCategory || !savedCategoryId ? {} : { contract_category_id: null }) } });
        setSavedTypeId(typeId);
        if (!keepCategory) setSavedCategoryId("");
      }
      if (deviceCatalog && deviceIds.join() !== savedDevices.map((item) => item.device_type_id).join()) {
        const kept = new Map(savedDevices.map((item) => [item.device_type_id, item]));
        const devices = await saveContractDeviceTypes(orgSlug, contractId, deviceIds.map((id) => ({
          device_type_id: id, quantity: kept.get(id)?.quantity ?? null, note: kept.get(id)?.note ?? null,
        })));
        const items = Array.isArray(devices?.items) ? devices.items : [];
        setSavedDevices(items);
        setDeviceIds(items.map((item) => item.device_type_id));
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
  const actions = loading ? null : <><button type="button" className="btn btn-primary btn-sm" onClick={() => void save()} disabled={saving}>{saving ? "Wird gespeichert…" : "Zuordnung speichern"}</button></>;
  return <CollapsibleSection id="cw-ownership" className="cw-ownership-section" title="Organisationszuordnung" description="Verantwortlichen Bereich, nutzende Bereiche, Gerätearten und zuständige Person festlegen." actions={actions}>
    {message ? <p className="cw-ownership-status" role="status">{message}</p> : null}
    {loading ? <p role="status">Zuordnung wird geladen…</p> : <div className="cw-ownership-grid">
      <p className="cw-ownership-group">Vertrag</p>
      <label><span>Vertragstyp</span><select value={typeId} onChange={(event) => setTypeId(event.target.value)}><option value="">Nicht festgelegt</option>{types.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>{types.length === 0 ? <small>Noch keine Vertragstypen angelegt. {isAdmin ? <Link href="/stammdaten/vertragstypen">Vertragstypen pflegen</Link> : null}</small> : null}</label>
      <label><span>Krankenhaus</span><select value={hospitalId} disabled={hospitalLocked} onChange={(event) => {
        setHospitalId(event.target.value);
        setResponsibleDepartmentId("");
        setBeneficiaryDepartmentIds([]);
        setCenterId("");
      }}><option value="">Organisationsweit</option>{hospitals.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{hospitalLocked ? <small>Das Krankenhaus lässt sich erst nach Aufheben der Bereichsrollen ändern.</small> : null}</label>
      <p className="cw-ownership-group">Abteilungen, Kostenstelle und Geräte</p>
      <label><span>Verantwortliche Abteilung</span><select value={responsibleDepartmentId} disabled={!hospitalId} onChange={(event) => {
        const next = event.target.value;
        setResponsibleDepartmentId(next);
        setBeneficiaryDepartmentIds((current) => current.filter((id) => id !== next));
        // Kostenstelle der Abteilung automatisch übernehmen (falls hinterlegt).
        setCenterId(centers.find((item) => item.department_id === next && item.hospital_id === hospitalId)?.id ?? "");
      }}><option value="">Bitte auswählen</option>{visibleDepartments.map((item) => <option key={item.id} value={item.id}>{departmentFullPath(item, departments)}</option>)}</select></label>
      <div className="cw-ownership-field"><span id="cw-beneficiary-label">Nutzende Abteilungen</span>
        <div className="cw-multi">{beneficiaryDepartmentIds.length ? <ul className="cw-people-chips" aria-labelledby="cw-beneficiary-label">{beneficiaryDepartmentIds.map((id) => {
          const department = departments.find((item) => item.id === id);
          const name = department ? departmentFullPath(department, departments) : "Unbekannter Bereich";
          return <li key={id}><span>{name}</span><button type="button" className="btn btn-ghost btn-sm" onClick={() => toggleBeneficiary(id)} aria-label={`${name} entfernen`}>✕</button></li>;
        })}</ul> : null}
        <select aria-label="Nutzende Abteilung hinzufügen" value="" disabled={!hospitalId || visibleDepartments.length === 0} onChange={(event) => { const id = event.target.value; if (id && !beneficiaryDepartmentIds.includes(id)) toggleBeneficiary(id); }}><option value="">+ Abteilung hinzufügen …</option>{visibleDepartments.filter((item) => item.id !== responsibleDepartmentId && !beneficiaryDepartmentIds.includes(item.id)).map((item) => <option key={item.id} value={item.id}>{departmentFullPath(item, departments)}</option>)}</select></div>
        {hospitalId && visibleDepartments.length === 0 ? <small>Für dieses Krankenhaus sind keine aktiven Abteilungen vorhanden.</small> : null}
      </div>
      <label><span>Kostenstelle</span><select value={centerId} onChange={(event) => {
        const next = event.target.value;
        setCenterId(next);
        // Kostenstelle einer verantwortlichen oder nutzenden Abteilung: Rollen bleiben, wie sie sind.
        // Gehört sie einer noch nicht gewählten Abteilung, wird diese verantwortlich (falls noch keine gewählt ist).
        const owner = centers.find((item) => item.id === next)?.department_id;
        if (owner && !selectedDepartments.has(owner) && !responsibleDepartmentId) {
          setResponsibleDepartmentId(owner);
          setBeneficiaryDepartmentIds((current) => current.filter((id) => id !== owner));
        }
      }} disabled={!hospitalId}><option value="">Keine Kostenstelle</option>{centerGroups.map((group) => group.items.length ? <optgroup key={group.label} label={group.label}>{group.items.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}{item.department_id ? ` — ${departmentFullPath(departments.find((department) => department.id === item.department_id)!, departments)}` : " — krankenhausweit"}</option>)}</optgroup> : null)}</select>{hospitalId && centerGroups[0].items.length === 0 && centerGroups[1].items.length === 0 && selectedDepartments.size ? <small>Die gewählten Abteilungen haben keine eigene Kostenstelle; unten stehen die übrigen des Krankenhauses.</small> : null}</label>
      {deviceCatalog ? <div className="cw-ownership-field"><span id="cw-devices-label">Gerätearten</span>
        <div className="cw-multi">{deviceIds.length ? <ul className="cw-people-chips" aria-labelledby="cw-devices-label">{deviceIds.map((id) => <li key={id}><span>{deviceLabel(id)}</span><button type="button" className="btn btn-ghost btn-sm" onClick={() => setDeviceIds((current) => current.filter((value) => value !== id))} aria-label={`${deviceLabel(id)} entfernen`}>✕</button></li>)}</ul> : null}
        {deviceGroups.length ? <select aria-label="Geräteart hinzufügen" value="" onChange={(event) => { const id = event.target.value; if (id) setDeviceIds((current) => current.includes(id) ? current : [...current, id]); }}><option value="">+ Geräteart hinzufügen …</option>{deviceGroups.map((group) => <optgroup key={group.label} label={group.label}>{group.items.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</optgroup>)}</select> : null}</div>
        <small>{selectedDepartments.size ? "Passende Gerätearten der gewählten Abteilungen stehen oben. " : ""}Anzahl und Notiz unter <Link href={contractHref(contractId, { tab: "relations" })}>Verknüpfungen → Geräte</Link>.</small>
      </div> : null}
      <p className="cw-ownership-group">Verantwortliche Personen</p>
      <div className="cw-ownership-field cw-ownership-people">
        <label><span>Hauptverantwortlich</span><select value={responsibleId} onChange={(event) => { const next = event.target.value; setResponsibleId(next); setFurtherIds((current) => current.filter((id) => id !== next)); }} disabled={assignees.length === 0}><option value="">Nicht zugewiesen</option>{personOptions(visibleAssignees, otherAssignees, new Set())}</select></label>
        <div className="cw-ownership-field"><span id="cw-further-label">Weitere Verantwortliche</span>
          <div className="cw-multi">{furtherIds.length ? <ul className="cw-people-chips" aria-labelledby="cw-further-label">{furtherIds.map((id) => <li key={id}><span>{assigneeName(id)}</span><button type="button" className="btn btn-ghost btn-sm" onClick={() => setFurtherIds((current) => current.filter((value) => value !== id))} aria-label={`${assigneeName(id)} entfernen`}>✕</button></li>)}</ul> : null}
          {assignees.length ? <select aria-label="Weitere verantwortliche Person hinzufügen" value="" onChange={(event) => { const id = event.target.value; if (id) setFurtherIds((current) => current.includes(id) ? current : [...current, id]); }}><option value="">+ Person hinzufügen …</option>{personOptions(visibleAssignees, otherAssignees, new Set([responsibleId, ...furtherIds]))}</select> : null}</div>
          <small>Erhalten dieselben Erinnerungen, sehen den Vertrag unter „Ich verantwortlich“ und dürfen ihn auch sehen, wenn er vertraulich ist.</small>
        </div>
        {assignees.length === 0 ? <p className="cw-ownership-note" role="note">In dieser Organisation gibt es noch keine Benutzer. {isAdmin ? <Link href="/settings/users">Benutzer anlegen</Link> : "Die Administration kann Benutzer anlegen."}</p> : null}
      </div>
      {roles?.unclassified_department_ids.length ? <p className="cw-ownership-note" role="note">Historische Zuordnung ohne dokumentierte Rolle: {roles.unclassified_department_ids.map((id) => {
        const department = departments.find((item) => item.id === id);
        return department ? departmentFullPath(department, departments) : "Unbekannter Bereich";
      }).join(" · ")}. Sie wird nicht automatisch als verantwortlich oder nutzend eingestuft.</p> : null}
    </div>}
  </CollapsibleSection>;
}
