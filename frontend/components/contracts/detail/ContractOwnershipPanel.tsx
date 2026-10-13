"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import ChipPicker, { type ChipPickerGroup } from "@/components/ui/ChipPicker";
import CollapsibleSection from "@/components/ui/CollapsibleSection";
import InlineAlert from "@/components/ui/InlineAlert";
import Signal from "@/components/ui/Signal";
import TagChip, { PersonTag, TagIcon } from "@/components/ui/TagChip";
import { useToast } from "@/components/ui/Toast";
import { useSaveShortcut, useUnsavedChanges } from "@/components/ui/useFormGuards";
import { getOrganizationStructure, listCostCenters } from "@/lib/domain-api/organizations";
import { listContractTypes, type ContractCategoryDto, type ContractTypeDto } from "@/lib/domain-api/catalogs";
import { getContractRegister, updateContractRegister } from "@/lib/domain-api/register";
import { departmentFullPath } from "@/lib/organization-tree";
import { SECTION_PARAM, contractHref } from "@/lib/fix-targets";
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
/** Gespeicherter Stand: Grundlage für „Ungespeicherte Änderungen“ und „Verwerfen“. */
type Snapshot = {
  typeId: string;
  hospitalId: string;
  responsibleDepartmentId: string;
  beneficiaryDepartmentIds: string[];
  centerId: string;
  responsibleId: string;
  furtherIds: string[];
  deviceIds: string[];
};

const EMPTY_SNAPSHOT: Snapshot = { typeId: "", hospitalId: "", responsibleDepartmentId: "", beneficiaryDepartmentIds: [], centerId: "", responsibleId: "", furtherIds: [], deviceIds: [] };

/** Gruppenkachel: Kennfarbe der Gruppe (Personen in der Kontofarbe, denn „partner“ ist der Lieferant). */
type GroupKind = "type" | "department" | "cost" | "person";
const PEOPLE_ICON = <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6" /></>;

function Icon({ children }: { children: ReactNode }) {
  return <svg className="cw-og-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{children}</svg>;
}

/** Gruppe: links Kachel, Titel und Zweck, rechts die Felder bzw. Werte. */
function Group({ id, kind, title, intro, children }: { id: string; kind: GroupKind; title: string; intro: string; children: ReactNode }) {
  return <section className="cw-og" aria-labelledby={id}>
    <div className="cw-og-intro">
      <span className={`cw-og-tile cw-og-tile--${kind}`}>{kind === "person" ? <Icon>{PEOPLE_ICON}</Icon> : <TagIcon kind={kind} className="cw-og-icon" />}</span>
      <div><h3 id={id}>{title}</h3><p>{intro}</p></div>
    </div>
    <div className="cw-og-body">{children}</div>
  </section>;
}


/** Kurzer Hinweis mit ⓘ unter genau dem Feld, das er betrifft. */
function Hint({ id, children }: { id?: string; children: ReactNode }) {
  return <p className="cw-hint" id={id}><Icon><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.5v.5" /></Icon><span>{children}</span></p>;
}

const optional = <span className="cw-of-optional"> · optional</span>;
const LOAD_FAILED = "Zuordnung konnte nicht geladen werden.";
const INTRO = {
  contract: "Art des Vertrags. Bestimmt Fristenregeln und Auswertungen.",
  cost: "Worauf die Kosten gebucht werden und welche Gerätearten der Vertrag abdeckt.",
  people: "Erhalten Erinnerungen zu Fristen und sehen den Vertrag unter „Ich verantwortlich“ – auch wenn er vertraulich ist.",
};

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
  const [saved, setSaved] = useState<Snapshot>(EMPTY_SNAPSHOT);
  const [editing, setEditing] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  // Zugänglicher Name des Hinzufügen-Knopfs, der nach „+ … hinzufügen“ den Fokus bekommt.
  const [focusAdd, setFocusAdd] = useState<string | null>(null);
  useEffect(() => {
    if (!editing || !focusAdd) return;
    document.getElementById("cw-ownership-body")?.querySelector<HTMLElement>(`[aria-label="${focusAdd}"]`)?.focus();
    setFocusAdd(null);
  }, [editing, focusAdd]);
  const toast = useToast();
  // „Ändern“/„Festlegen“ (Karte Zuständigkeit, Kopf, Hinweise) führt mit ?abschnitt=ownership hierher: gleich bearbeiten.
  const linkedSection = useSearchParams()?.get(SECTION_PARAM) ?? null;
  useEffect(() => {
    if (linkedSection === "ownership") { setEditing(true); setJustSaved(false); }
  }, [linkedSection]);

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
      setSaved({
        typeId: currentType,
        hospitalId: ownership.hospital_id ?? "",
        responsibleDepartmentId: departmentRoles.responsible_department_id ?? "",
        beneficiaryDepartmentIds: departmentRoles.beneficiary_department_ids ?? [],
        centerId: ownership.cost_center_id ?? "",
        responsibleId: ownership.responsible_account_id ?? "",
        furtherIds: ownership.further_responsible_account_ids ?? [],
        deviceIds: (devices ?? []).map((item) => item.device_type_id),
      });
    }).catch(() => { if (!cancelled) setMessage(LOAD_FAILED); })
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
      let deviceIdsAfterSave = deviceIds;
      if (deviceCatalog && deviceIds.join() !== savedDevices.map((item) => item.device_type_id).join()) {
        const kept = new Map(savedDevices.map((item) => [item.device_type_id, item]));
        const devices = await saveContractDeviceTypes(orgSlug, contractId, deviceIds.map((id) => ({
          device_type_id: id, quantity: kept.get(id)?.quantity ?? null, note: kept.get(id)?.note ?? null,
        })));
        const items = Array.isArray(devices?.items) ? devices.items : [];
        setSavedDevices(items);
        deviceIdsAfterSave = items.map((item) => item.device_type_id);
        setDeviceIds(deviceIdsAfterSave);
      }
      setAssignment(ownership);
      const nextFurther = furtherIds.filter((id) => id !== responsibleId);
      const nextBeneficiaries = responsibleDepartmentId ? beneficiaryDepartmentIds.filter((id) => id !== responsibleDepartmentId) : [];
      if (hospitalId && responsibleDepartmentId && roles) {
        setRoles({ ...roles, responsible_department_id: responsibleDepartmentId, beneficiary_department_ids: nextBeneficiaries });
      }
      setFurtherIds(nextFurther);
      setSaved({
        typeId, hospitalId, responsibleDepartmentId, beneficiaryDepartmentIds: nextBeneficiaries, centerId, responsibleId,
        furtherIds: nextFurther, deviceIds: deviceCatalog ? deviceIdsAfterSave : saved.deviceIds,
      });
      setEditing(false);
      setJustSaved(true);
      toast("Organisationszuordnung gespeichert.", "success");
      onSaved?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Zuordnung konnte nicht gespeichert werden.");
    } finally {
      setSaving(false);
    }
  }

  const current: Snapshot = { typeId, hospitalId, responsibleDepartmentId, beneficiaryDepartmentIds, centerId, responsibleId, furtherIds, deviceIds: deviceCatalog ? deviceIds : saved.deviceIds };
  const dirty = editing && JSON.stringify(current) !== JSON.stringify(saved);
  useUnsavedChanges(dirty);
  useSaveShortcut(dirty && !saving, () => void save());

  function startEdit() {
    setEditing(true);
    setJustSaved(false);
    setMessage("");
  }

  function discard() {
    setTypeId(saved.typeId);
    setHospitalId(saved.hospitalId);
    setResponsibleDepartmentId(saved.responsibleDepartmentId);
    setBeneficiaryDepartmentIds(saved.beneficiaryDepartmentIds);
    setCenterId(saved.centerId);
    setResponsibleId(saved.responsibleId);
    setFurtherIds(saved.furtherIds);
    setDeviceIds(saved.deviceIds);
    setMessage("");
    setEditing(false);
  }

  if (!editable) return null;

  const loadFailed = message === LOAD_FAILED;
  const departmentName = (id: string) => {
    const department = departments.find((item) => item.id === id);
    return department ? departmentFullPath(department, departments) : "Unbekannter Bereich";
  };
  const hospitalName = (id: string) => hospitals.find((item) => item.id === id)?.name ?? "Unbekanntes Krankenhaus";
  const typeLabel = (id: string) => types.find((item) => item.id === id)?.label ?? "Unbekannter Vertragstyp";
  const deviceText = (id: string) => {
    const quantity = savedDevices.find((item) => item.device_type_id === id)?.quantity;
    return quantity ? `${deviceLabel(id)} (${quantity})` : deviceLabel(id);
  };
  const none = <span className="cw-ov-none">Keine</span>;
  const notSet = <Signal tone="warning" size="sm">Nicht festgelegt</Signal>;
  const row = (label: string, value: ReactNode) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>;

  // Pflichtangaben der Zuordnung; grün nur, wenn wirklich alle gepflegt sind.
  const required: [string, string][] = [
    ["Vertragstyp", saved.typeId],
    ["Krankenhaus", saved.hospitalId],
    ["Verantwortliche Abteilung", saved.responsibleDepartmentId],
    ["Kostenstelle", saved.centerId],
    ["Hauptverantwortlich", saved.responsibleId],
  ];
  const missing = required.filter(([, value]) => !value).map(([label]) => label);
  const completeness = loading || loadFailed ? null : missing.length === 0
    ? <span className="cw-complete" title={`${required.map(([label]) => label).join(", ")}: alle erfasst`}>
      <svg className="cw-complete-ring" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle className="cw-complete-track" cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="9" /><path d="m8.5 12.3 2.3 2.3 4.7-4.8" /></svg>
      {required.length} von {required.length} Pflichtangaben
    </span>
    : <button type="button" className="cw-missing" onClick={startEdit} title={`Es fehlen: ${missing.join(", ")}`}>
      <Signal tone="warning" size="sm">{missing.length === 1 ? "1 Angabe fehlt" : `${missing.length} Angaben fehlen`}</Signal>
    </button>;
  const summary = loading || loadFailed ? null : <>
    <span>{saved.hospitalId ? <b>{hospitalName(saved.hospitalId)}</b> : "Organisationsweit"}</span>
    {saved.responsibleDepartmentId ? <><span className="sep" aria-hidden="true">·</span><span>{departmentName(saved.responsibleDepartmentId)}</span></> : null}
    {saved.responsibleId ? <><span className="sep" aria-hidden="true">·</span><span>{assigneeName(saved.responsibleId)}</span></> : null}
    {completeness}
  </>;
  const description = <>Wem der Vertrag gehört, wer ihn nutzt und wer zuständig ist{completeness ? <> {completeness}</> : null}{justSaved ? <> <Signal tone="done" size="sm">Gespeichert</Signal></> : null}</>;
  const actions = loading || loadFailed
    ? null
    : !editing
      ? <button type="button" className="btn btn-sm" onClick={startEdit} aria-label="Organisationszuordnung bearbeiten">
        <svg className="btn-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></svg>Bearbeiten
      </button>
      : dirty ? null : <button type="button" className="btn btn-ghost btn-sm" onClick={discard}>Abbrechen</button>;

  const beneficiaryGroups: ChipPickerGroup[] = [{
    label: hospitalId ? `Abteilungen · ${hospitalName(hospitalId)}` : "Abteilungen",
    options: visibleDepartments
      .filter((item) => item.id !== responsibleDepartmentId && !beneficiaryDepartmentIds.includes(item.id))
      .map((item) => ({ value: item.id, label: departmentFullPath(item, departments) })),
  }];
  const exclude = new Set([responsibleId, ...furtherIds]);
  const personGroups: ChipPickerGroup[] = [
    { label: "Passend zur Zuordnung", options: visibleAssignees.filter((item) => !exclude.has(item.id)).map((item) => ({ value: item.id, label: item.display_name })) },
    { label: "Weitere Benutzer der Organisation", options: otherAssignees.filter((item) => !exclude.has(item.id)).map((item) => ({ value: item.id, label: item.display_name })) },
  ];
  const noHospital = "Zuerst ein Krankenhaus wählen";
  const orgIntro = "Wer den Vertrag verantwortet und welche Bereiche ihn nutzen.";

  const savedCenter = centers.find((item) => item.id === saved.centerId);
  const roleWord = (word: string) => <span className="cw-ov-role">{word}</span>;
  // „+ … hinzufügen“ statt nur „Keine“: öffnet Bearbeiten und setzt den Fokus auf die Auswahl.
  const addButton = (label: string, target: string) => editable
    ? <button type="button" className="cw-ov-add" onClick={() => { startEdit(); setFocusAdd(target); }}>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5v14M5 12h14" /></svg>{label}
    </button>
    : null;

  const view = <div className="cw-ov-groups">
    <Group id="cw-og-contract" kind="type" title="Vertrag" intro={INTRO.contract}>
      <dl className="cw-ov">{row("Vertragstyp", saved.typeId ? <TagChip kind="type">{typeLabel(saved.typeId)}</TagChip> : notSet)}</dl>
    </Group>
    <Group id="cw-og-org" kind="department" title="Krankenhaus & Abteilungen" intro={orgIntro}>
      <dl className="cw-ov">
        {row("Krankenhaus", <span className="cw-ov-plain"><TagIcon kind="partner" className="cw-og-icon" />{saved.hospitalId ? hospitalName(saved.hospitalId) : "Organisationsweit"}</span>)}
        {row("Verantwortliche Abteilung", saved.responsibleDepartmentId ? <><TagChip kind="department">{departmentName(saved.responsibleDepartmentId)}</TagChip>{roleWord("verantwortlich")}</> : notSet)}
        {row("Nutzende Abteilungen", saved.beneficiaryDepartmentIds.length
          ? <>{saved.beneficiaryDepartmentIds.map((id) => <TagChip key={id} kind="department">{departmentName(id)}</TagChip>)}{roleWord("nutzend")}</>
          : <>{none}{addButton("Abteilung hinzufügen", "Nutzende Abteilung hinzufügen")}</>)}
      </dl>
    </Group>
    <Group id="cw-og-cost" kind="cost" title="Kostenstelle & Geräte" intro={INTRO.cost}>
      <dl className="cw-ov">
        {row("Kostenstelle", saved.centerId ? savedCenter ? <TagChip kind="cost" code={savedCenter.code}>{savedCenter.name}</TagChip> : "Unbekannte Kostenstelle" : notSet)}
        {deviceCatalog ? row("Gerätearten", saved.deviceIds.length ? saved.deviceIds.map((id) => <TagChip key={id} kind="device">{deviceText(id)}</TagChip>) : none) : null}
      </dl>
    </Group>
    <Group id="cw-og-people" kind="person" title="Verantwortliche Personen" intro={INTRO.people}>
      <dl className="cw-ov">
        {row("Hauptverantwortlich", saved.responsibleId ? <PersonTag name={assigneeName(saved.responsibleId)} /> : notSet)}
        {row("Weitere Verantwortliche", saved.furtherIds.length
          ? saved.furtherIds.map((id) => <PersonTag key={id} name={assigneeName(id)} />)
          : <>{none}{addButton("Person hinzufügen", "Weitere verantwortliche Person hinzufügen")}</>)}
      </dl>
    </Group>
  </div>;

  const edit = <>
    <Group id="cw-og-contract" kind="type" title="Vertrag" intro={INTRO.contract}>
      <div className="cw-of">
        <label htmlFor="cw-own-type">Vertragstyp</label>
        <select id="cw-own-type" value={typeId} onChange={(event) => setTypeId(event.target.value)}><option value="">Nicht festgelegt</option>{types.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
        {types.length === 0 ? <Hint>Noch keine Vertragstypen angelegt. {isAdmin ? <Link href="/stammdaten/vertragstypen">Vertragstypen pflegen</Link> : null}</Hint> : null}
      </div>
    </Group>
    <Group id="cw-og-org" kind="department" title="Krankenhaus & Abteilungen" intro={`${orgIntro} Die Auswahl bestimmt die Vorschläge für Kostenstelle, Gerätearten und Personen.`}>
      <div className="cw-of">
        {hospitalLocked ? <>
          <span className="cw-of-label" id="cw-own-hospital-label">Krankenhaus</span>
          <div className="cw-locked" role="group" aria-labelledby="cw-own-hospital-label" aria-describedby="cw-own-hospital-hint">
            <span><Icon><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></Icon>{hospitalId ? hospitalName(hospitalId) : "Organisationsweit"}</span>
            <span className="cw-locked-word">gesperrt</span>
          </div>
          <Hint id="cw-own-hospital-hint">Änderbar, sobald keine Abteilungen mehr zugeordnet sind. <button type="button" className="cw-hint-link" onClick={() => document.getElementById("cw-own-responsible")?.focus()}>Abteilungen ansehen</button></Hint>
        </> : <>
          <label htmlFor="cw-own-hospital">Krankenhaus</label>
          <select id="cw-own-hospital" value={hospitalId} onChange={(event) => {
            setHospitalId(event.target.value);
            setResponsibleDepartmentId("");
            setBeneficiaryDepartmentIds([]);
            setCenterId("");
          }}><option value="">Organisationsweit</option>{hospitals.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        </>}
      </div>
      <div className="cw-of">
        {hospitalId ? <>
          <label htmlFor="cw-own-responsible">Verantwortliche Abteilung</label>
          <select id="cw-own-responsible" value={responsibleDepartmentId} onChange={(event) => {
            const next = event.target.value;
            setResponsibleDepartmentId(next);
            setBeneficiaryDepartmentIds((list) => list.filter((id) => id !== next));
            // Kostenstelle der Abteilung automatisch übernehmen (falls hinterlegt).
            setCenterId(centers.find((item) => item.department_id === next && item.hospital_id === hospitalId)?.id ?? "");
          }}><option value="">Bitte auswählen</option>{visibleDepartments.map((item) => <option key={item.id} value={item.id}>{departmentFullPath(item, departments)}</option>)}</select>
          {visibleDepartments.length === 0 ? <Hint>Für dieses Krankenhaus sind keine aktiven Abteilungen vorhanden.</Hint> : null}
        </> : <><span className="cw-of-label">Verantwortliche Abteilung</span><Hint>{noHospital}</Hint></>}
      </div>
      <div className="cw-of">
        <span className="cw-of-label" id="cw-beneficiary-label">Nutzende Abteilungen{optional}</span>
        <ChipPicker
          labelId="cw-beneficiary-label"
          items={beneficiaryDepartmentIds.map((id) => ({ id, label: departmentName(id) }))}
          onRemove={toggleBeneficiary}
          groups={beneficiaryGroups}
          onAdd={(id) => { if (!beneficiaryDepartmentIds.includes(id)) toggleBeneficiary(id); }}
          addLabel="Abteilung"
          addAriaLabel="Nutzende Abteilung hinzufügen"
          disabledHint={hospitalId ? null : noHospital}
        />
      </div>
    </Group>
    <Group id="cw-og-cost" kind="cost" title="Kostenstelle & Geräte" intro={INTRO.cost}>
      <div className="cw-of">
        {hospitalId ? <>
          <label htmlFor="cw-own-center">Kostenstelle</label>
          <select id="cw-own-center" value={centerId} onChange={(event) => {
            const next = event.target.value;
            setCenterId(next);
            // Kostenstelle einer verantwortlichen oder nutzenden Abteilung: Rollen bleiben, wie sie sind.
            // Gehört sie einer noch nicht gewählten Abteilung, wird diese verantwortlich (falls noch keine gewählt ist).
            const owner = centers.find((item) => item.id === next)?.department_id;
            if (owner && !selectedDepartments.has(owner) && !responsibleDepartmentId) {
              setResponsibleDepartmentId(owner);
              setBeneficiaryDepartmentIds((list) => list.filter((id) => id !== owner));
            }
          }}><option value="">Keine Kostenstelle</option>{centerGroups.map((group) => group.items.length ? <optgroup key={group.label} label={group.label}>{group.items.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}{item.department_id ? ` — ${departmentFullPath(departments.find((department) => department.id === item.department_id)!, departments)}` : " — krankenhausweit"}</option>)}</optgroup> : null)}</select>
          {centerGroups[0].items.length === 0 && centerGroups[1].items.length === 0 && selectedDepartments.size
            ? <Hint>Die gewählten Abteilungen haben keine eigene Kostenstelle; unten stehen die übrigen des Krankenhauses.</Hint>
            : selectedDepartments.size ? <Hint>Kostenstellen der gewählten Abteilungen stehen oben.</Hint> : null}
        </> : <><span className="cw-of-label">Kostenstelle</span><Hint>{noHospital}</Hint></>}
      </div>
      {deviceCatalog ? <div className="cw-of">
        <span className="cw-of-label" id="cw-devices-label">Gerätearten{optional}</span>
        <ChipPicker
          labelId="cw-devices-label"
          items={deviceIds.map((id) => ({ id, label: deviceLabel(id) }))}
          onRemove={(id) => setDeviceIds((list) => list.filter((value) => value !== id))}
          groups={deviceGroups.map((group) => ({ label: group.label, options: group.items.map((item) => ({ value: item.id, label: item.label })) }))}
          onAdd={(id) => setDeviceIds((list) => list.includes(id) ? list : [...list, id])}
          addLabel="Geräteart"
          addAriaLabel="Geräteart hinzufügen"
        />
        <Hint>Anzahl und Notiz je Geräteart: <Link href={contractHref(contractId, { tab: "relations" })}>Verknüpfungen › Geräte</Link></Hint>
      </div> : null}
    </Group>
    <Group id="cw-og-people" kind="person" title="Verantwortliche Personen" intro={INTRO.people}>
      <div className="cw-of">
        <label htmlFor="cw-own-person">Hauptverantwortlich</label>
        <select id="cw-own-person" value={responsibleId} onChange={(event) => { const next = event.target.value; setResponsibleId(next); setFurtherIds((list) => list.filter((id) => id !== next)); }} disabled={assignees.length === 0}><option value="">Nicht zugewiesen</option>{personOptions(visibleAssignees, otherAssignees, new Set())}</select>
        {assignees.length === 0 ? <Hint>In dieser Organisation gibt es noch keine Benutzer. {isAdmin ? <Link href="/settings/users">Benutzer anlegen</Link> : "Die Administration kann Benutzer anlegen."}</Hint> : null}
      </div>
      <div className="cw-of">
        <span className="cw-of-label" id="cw-further-label">Weitere Verantwortliche{optional}</span>
        <ChipPicker
          labelId="cw-further-label"
          items={furtherIds.map((id) => ({ id, label: assigneeName(id) }))}
          onRemove={(id) => setFurtherIds((list) => list.filter((value) => value !== id))}
          groups={personGroups}
          onAdd={(id) => setFurtherIds((list) => list.includes(id) ? list : [...list, id])}
          addLabel="Person"
          addAriaLabel="Weitere verantwortliche Person hinzufügen"
        />
      </div>
    </Group>
  </>;

  return <CollapsibleSection id="cw-ownership" className="cw-ownership-section" title="Organisationszuordnung" description={description} summary={summary} actions={actions} forceOpen={editing}>
    {loading ? <p role="status" className="cw-ownership-loading">Zuordnung wird geladen…</p> : loadFailed ? <div className="cw-ownership-alert"><InlineAlert tone="critical" role="alert">{message}</InlineAlert></div> : <>
      {editing ? edit : view}
      {roles?.unclassified_department_ids.length ? <p className="cw-ownership-note" role="note">Historische Zuordnung ohne dokumentierte Rolle: {roles.unclassified_department_ids.map(departmentName).join(" · ")}. Sie wird nicht automatisch als verantwortlich oder nutzend eingestuft.</p> : null}
      {editing && message ? <div className="cw-ownership-alert"><InlineAlert tone="critical" role="alert">{message}</InlineAlert></div> : null}
      {dirty ? <div className="cw-savebar" role="region" aria-label="Änderungen speichern">
        <div className="cw-savebar-msg"><Signal tone="info" size="sm">Ungespeicherte Änderungen</Signal><span><kbd>Strg</kbd> + <kbd>S</kbd> speichert</span></div>
        <div className="cw-savebar-actions">
          <button type="button" className="btn btn-ghost" onClick={discard} disabled={saving}>Verwerfen</button>
          <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving} aria-keyshortcuts="Control+S">{saving ? "Wird gespeichert…" : "Zuordnung speichern"}</button>
        </div>
      </div> : null}
    </>}
  </CollapsibleSection>;
}
