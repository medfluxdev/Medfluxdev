"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { importDocuments, retryDocument } from "@/lib/domain-api/documents";
import { useAuth } from "@/components/auth/AuthProvider";
import { ImportFileResult, ImportStatus } from "@/lib/types";
import Button from "@/components/ui/Button";
import InlineAlert from "@/components/ui/InlineAlert";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge, { StatusTone } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { getOrganizationStructure, listCostCenters, type CostCenterDto, type OrganizationStructureDto } from "@/lib/domain-api/organizations";
import { departmentFullPath } from "@/lib/organization-tree";
import AttachToExistingContract from "@/components/contracts/AttachToExistingContract";

const statusLabel: Record<ImportStatus, string> = {
  imported: "Importiert",
  duplicate: "Duplikat",
  rejected: "Abgelehnt",
  failed: "Import fehlgeschlagen",
  analysis_failed: "Importiert – Analyse fehlgeschlagen",
};

const statusTone: Record<ImportStatus, StatusTone> = {
  imported: "success",
  duplicate: "warning",
  rejected: "critical",
  failed: "critical",
  analysis_failed: "critical",
};

function supportedFile(file: File) {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".docx");
}

function analysisLabel(result: ImportFileResult): string {
  if (result.status === "duplicate") return "Nicht erneut analysiert";
  if (result.status === "rejected" || result.status === "failed") return "Nicht gestartet";
  if (result.status === "analysis_failed" || result.analysis_status === "failed") return "Fehlgeschlagen";
  if (result.analysis_status === "partial") return "Teilanalyse – Prüfung erforderlich";
  if (result.analysis_status === "success") return "Erfolgreich";
  return "Status nicht gemeldet";
}

export default function ImportPage() {
  const { organizationSlug, membership } = useAuth();
  const canAssign = membership?.role === "admin" || membership?.role === "contract_manager";
  const [organizationStructure, setOrganizationStructure] = useState<OrganizationStructureDto>({ hospitals: [], departments: [] });
  const [costCenters, setCostCenters] = useState<CostCenterDto[]>([]);
  const [assignmentLoading, setAssignmentLoading] = useState(false);
  const [assignmentError, setAssignmentError] = useState<string | null>(null);
  const [hospitalId, setHospitalId] = useState("");
  const [responsibleDepartmentId, setResponsibleDepartmentId] = useState("");
  const [beneficiaryDepartmentIds, setBeneficiaryDepartmentIds] = useState<string[]>([]);
  const [costCenterId, setCostCenterId] = useState("");
  const [selected, setSelected] = useState<File[]>([]);
  const [rejectedSelection, setRejectedSelection] = useState<string[]>([]);
  const [results, setResults] = useState<ImportFileResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [destination, setDestination] = useState<"new" | "existing">("new");
  const [step, setStep] = useState(1);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const effectiveOrgSlug = organizationSlug ?? membership?.organization_slug ?? "krankenhaus";

  useEffect(() => {
    if (!canAssign) return;
    let active = true;
    setAssignmentLoading(true);
    Promise.all([getOrganizationStructure(effectiveOrgSlug), listCostCenters(effectiveOrgSlug)])
      .then(([structure, centers]) => {
        if (!active) return;
        setOrganizationStructure(structure);
        setCostCenters(centers.items);
        const preferredHospital = membership?.hospital_id ?? window.localStorage.getItem("medflux.hospitalId") ?? "";
        const validHospital = structure.hospitals.some((item) => item.id === preferredHospital && item.is_active)
          ? preferredHospital
          : structure.hospitals.find((item) => item.is_active)?.id ?? "";
        setHospitalId(validHospital);
        setResponsibleDepartmentId(membership?.department_id ?? "");
      })
      .catch(() => { if (active) setAssignmentError("Die Organisationsstruktur konnte nicht geladen werden. Die Zuordnung ist derzeit nicht verfügbar."); })
      .finally(() => { if (active) setAssignmentLoading(false); });
    return () => { active = false; };
  }, [canAssign, effectiveOrgSlug, membership?.department_id, membership?.hospital_id]);

  const availableDepartments = useMemo(
    () => organizationStructure.departments.filter((item) => item.is_active && item.hospital_id === hospitalId),
    [organizationStructure.departments, hospitalId],
  );
  const availableCostCenters = useMemo(
    () => costCenters.filter((item) => item.is_active && item.hospital_id === hospitalId && (!item.department_id || item.department_id === responsibleDepartmentId)),
    [costCenters, hospitalId, responsibleDepartmentId],
  );

  const addFiles = useCallback((list: FileList | null) => {
    if (!list) return;
    const incoming = Array.from(list);
    const accepted = incoming.filter(supportedFile);
    const rejected = incoming.filter((file) => !supportedFile(file)).map((file) => file.name);
    setResults(null);
    setError(null);
    setRejectedSelection(rejected);
    setSelected((prev) => [...prev, ...accepted]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setSelected((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handleDropzoneKey = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      inputRef.current?.click();
    }
  }, []);

  const handleUpload = useCallback(async () => {
    if (selected.length === 0 || loading) return;
    if (canAssign && assignmentLoading) return;
    if (canAssign && assignmentError) {
      setError("Bitte warten Sie, bis die Organisationszuordnung wieder verfügbar ist.");
      return;
    }
    if (canAssign && beneficiaryDepartmentIds.length > 0 && !responsibleDepartmentId) {
      setError("Bitte legen Sie zuerst den verantwortlichen Bereich fest.");
      return;
    }
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await importDocuments(selected, effectiveOrgSlug, canAssign && hospitalId ? {
        hospital_id: hospitalId,
        responsible_department_id: responsibleDepartmentId || undefined,
        beneficiary_department_ids: beneficiaryDepartmentIds,
        cost_center_id: costCenterId || undefined,
      } : undefined);
      setResults(res.documents);
      setSelected([]);
      setRejectedSelection([]);
    } catch (err) {
      setError(err instanceof Error ? `Import fehlgeschlagen: ${err.message}` : "Import fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }, [selected, loading, effectiveOrgSlug, canAssign, assignmentLoading, assignmentError, hospitalId, responsibleDepartmentId, beneficiaryDepartmentIds, costCenterId]);

  const importAcceptedCount = useMemo(
    () => results?.filter((r) => r.status === "imported" || r.status === "analysis_failed").length ?? 0,
    [results]
  );
  const analysisSuccessCount = useMemo(
    () => results?.filter((r) => r.analysis_status === "success").length ?? 0,
    [results]
  );
  const analysisFailedCount = useMemo(
    () => results?.filter((r) => r.status === "analysis_failed" || r.analysis_status === "failed").length ?? 0,
    [results]
  );
  const duplicateCount = useMemo(
    () => results?.filter((r) => r.status === "duplicate").length ?? 0,
    [results]
  );
  const reviewCount = useMemo(
    () => results?.filter((r) => (r.status === "imported" || r.status === "analysis_failed") && r.requires_review).length ?? 0,
    [results]
  );

  const canRetry = (r: ImportFileResult): boolean =>
    (r.status === "analysis_failed" || r.analysis_status === "failed") && !!r.document_version_id;

  const retryAnalysis = useCallback(async (r: ImportFileResult) => {
    if (!r.document_version_id || retryingId) return;
    setRetryingId(r.document_version_id);
    try {
      const res = await retryDocument(r.document_version_id, effectiveOrgSlug);
      setResults((prev) => prev ? prev.map((x) => x.document_version_id === r.document_version_id ? {
        ...x,
        status: res.status === "imported" || res.analysis_status === "success" ? "imported" : res.status === "analysis_failed" || res.analysis_status === "failed" ? "analysis_failed" : x.status,
        analysis_status: res.analysis_status ?? x.analysis_status,
        message: res.message ?? (res.analysis_status === "success" ? "Analyse erneut erfolgreich." : "Analyse erneut fehlgeschlagen."),
        contract_id: res.contract_id ?? x.contract_id,
      } : x) : prev);
      toast(
        res.analysis_status === "success" || res.status === "imported"
          ? `Analyse für „${r.original_filename}“ erneut erfolgreich.`
          : `Analyse für „${r.original_filename}“ erneut fehlgeschlagen.`,
        res.analysis_status === "success" || res.status === "imported" ? "success" : "error"
      );
    } catch {
      toast(`Erneute Analyse für „${r.original_filename}“ konnte nicht gestartet werden.`, "error");
    } finally {
      setRetryingId(null);
    }
  }, [effectiveOrgSlug, retryingId, toast]);

  const STEPS = ["Ziel", "Dateien", "Prüfen & starten", "Ergebnis"];
  const hospitalName = organizationStructure.hospitals.find((item) => item.id === hospitalId)?.name;
  const departmentName = availableDepartments.find((item) => item.id === responsibleDepartmentId);
  const costCenterName = availableCostCenters.find((item) => item.id === costCenterId);
  const goTo = (next: number) => { setError(null); setStep(next); };

  async function startImport() {
    if (canAssign && beneficiaryDepartmentIds.length > 0 && !responsibleDepartmentId) {
      setError("Bitte legen Sie zuerst den verantwortlichen Bereich fest.");
      return;
    }
    await handleUpload();
    setStep(4);
  }

  return (
    <div className="page">
      <PageHeader
        title="Verträge importieren"
        description="PDF- oder DOCX-Dateien hinzufügen. Import und Analyse laufen vollständig lokal und werden getrennt ausgewiesen."
      />

      <div className="import-layout">
        <div className="stack-4">
          <ol className="wizard-steps" aria-label="Schritte des Imports">
            {STEPS.map((label, index) => (
              <li key={label} className={index + 1 === step ? "is-current" : index + 1 < step ? "is-done" : undefined} aria-current={index + 1 === step ? "step" : undefined}>
                <span className="wizard-step-number" aria-hidden="true">{index + 1}</span>{label}
              </li>
            ))}
          </ol>

          {step === 1 ? (
            <section className="card card-pad stack-4" aria-labelledby="wizard-target">
              <h2 id="wizard-target">Wohin gehören die Dateien?</h2>
              <div className="import-scope-card" role="note" aria-label="Zielbereich des Imports">
                <strong>Zielbereich</strong>
                <span>{membership?.organization_name ?? effectiveOrgSlug}</span>
              </div>
              {canAssign ? (
                <fieldset className="wizard-choices">
                  <legend className="visually-hidden">Ziel der Dateien</legend>
                  <label className="wizard-choice"><input type="radio" name="import-destination" checked={destination === "new"} onChange={() => setDestination("new")} /><span><strong>Neuen Vertrag anlegen</strong><small>Die lokale KI liest das Dokument und schlägt Stammdaten vor. Unklare Angaben werden zur Prüfung markiert, nichts wird erfunden.</small></span></label>
                  <label className="wizard-choice"><input type="radio" name="import-destination" checked={destination === "existing"} onChange={() => setDestination("existing")} /><span><strong>Zu bestehendem Vertrag hinzufügen</strong><small>Nachtrag, Kündigung oder Anlage. Änderungen werden nur als Vorschlag angezeigt.</small></span></label>
                  <Link href="/contracts/new" className="wizard-choice wizard-choice-link"><span><strong>Ohne Dokument manuell erfassen</strong><small>Vertrag direkt in den Stammdaten anlegen.</small></span></Link>
                </fieldset>
              ) : null}

              {destination === "existing" ? <AttachToExistingContract organizationSlug={effectiveOrgSlug} /> : <>
                {canAssign && (
                  <fieldset className="import-assignment-card" disabled={assignmentLoading || loading || organizationStructure.hospitals.filter((item) => item.is_active).length === 0}>
                    <legend>Vertragszuordnung beim Import</legend>
                    <p>Die Auswahl wird bei neuen Verträgen gespeichert. Duplikate werden nicht neu zugeordnet.</p>
                    {assignmentError && <InlineAlert tone="critical" role="alert">{assignmentError}</InlineAlert>}
                    {!assignmentError && organizationStructure.hospitals.every((item) => !item.is_active) && !assignmentLoading && <p role="status">Es ist kein aktives Krankenhaus eingerichtet. Die Zuordnung kann unter Organisationseinstellungen eingerichtet werden.</p>}
                    <div className="form-grid">
                      <label className="field">Krankenhaus
                        <select aria-label="Krankenhaus für Import" value={hospitalId} onChange={(event) => { setHospitalId(event.target.value); setResponsibleDepartmentId(""); setBeneficiaryDepartmentIds([]); setCostCenterId(""); }}>
                          <option value="">Krankenhaus wählen</option>
                          {organizationStructure.hospitals.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                        </select>
                      </label>
                      <label className="field">Verantwortlicher Bereich
                        <select aria-label="Verantwortlicher Bereich für Import" value={responsibleDepartmentId} disabled={!hospitalId} onChange={(event) => { setResponsibleDepartmentId(event.target.value); setCostCenterId(""); }}>
                          <option value="">Nicht festgelegt</option>
                          {availableDepartments.map((item) => <option key={item.id} value={item.id}>{departmentFullPath(item, availableDepartments)}</option>)}
                        </select>
                      </label>
                      <label className="field">Nutzende Bereiche
                        <select aria-label="Nutzende Bereiche für Import" multiple value={beneficiaryDepartmentIds} disabled={!hospitalId} onChange={(event) => setBeneficiaryDepartmentIds(Array.from(event.target.selectedOptions, (option) => option.value))}>
                          {availableDepartments.filter((item) => item.id !== responsibleDepartmentId).map((item) => <option key={item.id} value={item.id}>{departmentFullPath(item, availableDepartments)}</option>)}
                        </select>
                      </label>
                      <label className="field">Kostenstelle
                        <select aria-label="Kostenstelle für Import" value={costCenterId} disabled={!hospitalId} onChange={(event) => setCostCenterId(event.target.value)}>
                          <option value="">Nicht festgelegt</option>
                          {availableCostCenters.map((item) => <option key={item.id} value={item.id}>{item.code} – {item.name}</option>)}
                        </select>
                      </label>
                    </div>
                  </fieldset>
                )}
                <div className="form-actions"><Button variant="primary" onClick={() => goTo(2)} disabled={canAssign && assignmentLoading}>Weiter zu den Dateien</Button></div>
              </>}
            </section>
          ) : null}

          {step === 2 ? (
            <section className="card card-pad stack-4" aria-labelledby="wizard-files">
              <h2 id="wizard-files">Dateien auswählen</h2>
              <div
                className="dropzone"
                role="button"
                tabIndex={0}
                aria-label="Dateien hinzufügen. Klicken oder Dateien hierher ziehen."
                onClick={() => inputRef.current?.click()}
                onKeyDown={handleDropzoneKey}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
              >
                <p className="dz-primary">Dateien hierher ziehen oder klicken</p>
                <p>Unterstützte Dateitypen: <strong>PDF</strong> und <strong>DOCX</strong></p>
                <input ref={inputRef} type="file" multiple accept=".pdf,.docx" hidden onChange={(e) => addFiles(e.target.files)} />
              </div>
              {rejectedSelection.length > 0 && (
                <InlineAlert tone="critical" role="alert">
                  Nicht unterstützte Dateien wurden nicht hinzugefügt: {rejectedSelection.join(", ")}. Erlaubt sind PDF und DOCX.
                </InlineAlert>
              )}
              {selected.length > 0 ? (
                <ul className="file-list" aria-label="Ausgewählte Dateien">
                  {selected.map((file, i) => (
                    <li key={`${file.name}-${i}`} className="file-row">
                      <span className="file-name">{file.name}</span>
                      <span className="file-meta">{(file.size / 1024).toFixed(1)} KB</span>
                      <Button size="sm" variant="danger" onClick={() => removeFile(i)}>Entfernen</Button>
                    </li>
                  ))}
                </ul>
              ) : <p className="state-empty">Noch keine Dateien ausgewählt. Wählen Sie eine oder mehrere Wartungs- oder Serviceverträge aus.</p>}
              <div className="form-actions">
                <Button onClick={() => goTo(1)}>Zurück</Button>
                <Button variant="primary" disabled={selected.length === 0} onClick={() => goTo(3)}>Weiter zur Prüfung ({selected.length})</Button>
              </div>
            </section>
          ) : null}

          {step === 3 ? (
            <section className="card card-pad stack-4" aria-labelledby="wizard-confirm">
              <h2 id="wizard-confirm">Angaben prüfen und Import starten</h2>
              <dl className="quick-facts">
                <div><dt>Ziel</dt><dd>Neuer Vertrag je Datei</dd></div>
                <div><dt>Dateien</dt><dd>{selected.length}</dd></div>
                {canAssign ? <div><dt>Krankenhaus</dt><dd>{hospitalName ?? "Nicht festgelegt"}</dd></div> : null}
                {canAssign ? <div><dt>Verantwortlicher Bereich</dt><dd>{departmentName ? departmentFullPath(departmentName, availableDepartments) : "Nicht festgelegt"}</dd></div> : null}
                {canAssign ? <div><dt>Nutzende Bereiche</dt><dd>{beneficiaryDepartmentIds.length || "Keine"}</dd></div> : null}
                {canAssign ? <div><dt>Kostenstelle</dt><dd>{costCenterName ? `${costCenterName.code} – ${costCenterName.name}` : "Nicht festgelegt"}</dd></div> : null}
              </dl>
              <InlineAlert tone="info">Die Analyse läuft lokal auf diesem Rechner. Unklare oder widersprüchliche Angaben werden nicht automatisch bestätigt, sondern zur Prüfung markiert.</InlineAlert>
              {error && <InlineAlert tone="critical" role="alert">{error}</InlineAlert>}
              <div className="form-actions">
                <Button onClick={() => goTo(2)} disabled={loading}>Zurück</Button>
                <Button variant="primary" loading={loading} loadingLabel="Wird importiert…" onClick={() => void startImport()}>Import starten ({selected.length})</Button>
              </div>
              {loading && (
                <div role="status" aria-live="polite">
                  <p><strong>Dateien werden übertragen und lokal verarbeitet.</strong></p>
                  <ul className="import-processing-steps" aria-label="Verarbeitungsschritte">
                    <li>Übertragung</li><li>Lesen/OCR bei Bedarf</li><li>Extraktion</li><li>Analyse</li><li>Fristen/Kosten</li>
                  </ul>
                  <div className="import-progress" aria-hidden="true"><div className="import-progress-bar import-progress-active" /></div>
                </div>
              )}
            </section>
          ) : null}

          {step === 4 ? (
            <section className="card card-pad stack-4" aria-label="Import-Ergebnis" aria-live="polite">
              <h2 className="card-title">Import-Ergebnis</h2>
              {error && <InlineAlert tone="critical" role="alert">{error}</InlineAlert>}
              {results && results.length > 0 ? <>
                <div className="import-result-summary">
                  <div><strong>{importAcceptedCount}</strong><span>importiert</span></div>
                  <div><strong>{analysisSuccessCount}</strong><span>Analyse erfolgreich</span></div>
                  <div><strong>{analysisFailedCount}</strong><span>Analyse fehlgeschlagen</span></div>
                  <div><strong>{duplicateCount}</strong><span>Duplikate</span></div>
                </div>
                {reviewCount > 0 && <InlineAlert tone="warning" role="status">{reviewCount} {reviewCount === 1 ? "Vertrag erfordert" : "Verträge erfordern"} manuelle Prüfung.</InlineAlert>}
                <div className="result-list">
                  {results.map((r, i) => (
                    <div key={`${r.document_version_id ?? r.original_filename}-${i}`} className="result-row">
                      <span className="result-file">{r.original_filename}</span>
                      <div className="result-state-stack">
                        <div className="result-state-line"><span className="result-state-label">Import</span><StatusBadge tone={statusTone[r.status]} label={statusLabel[r.status]} /></div>
                        <div className="result-state-line"><span className="result-state-label">Analyse</span><span className="result-state-value">{analysisLabel(r)}</span></div>
                        {r.requires_review && <div className="result-state-line"><span className="result-state-label">Prüfung</span><span className="result-state-value">Erforderlich</span></div>}
                      </div>
                      {r.message && <span className="result-msg">{r.message}</span>}
                      {canRetry(r) && <Button size="sm" disabled={retryingId === r.document_version_id} onClick={() => void retryAnalysis(r)}>{retryingId === r.document_version_id ? "Wird erneut verarbeitet…" : "Analyse erneut starten"}</Button>}
                      {r.contract_id && r.requires_review ? (
                        <Link href={`/contracts/${r.contract_id}?tab=documents&subtab=review`} className="result-link">Zur manuellen Prüfung</Link>
                      ) : r.contract_id ? (
                        <Link href={`/contracts/${r.contract_id}`} className="result-link">Vertrag ansehen</Link>
                      ) : null}
                    </div>
                  ))}
                </div>
              </> : null}
              <div className="form-actions">
                <Button onClick={() => { setResults(null); goTo(2); }}>Weitere Dateien importieren</Button>
                <Link href="/register" className="btn btn-primary">Zur Vertragsliste</Link>
              </div>
            </section>
          ) : null}
        </div>

        <aside className="card card-pad side-note">
          <h2>Hinweise zum Import</h2>
          <ul>
            <li>Importiert bedeutet, dass das Dokument angenommen und gespeichert wurde; der Analysestatus wird separat angezeigt.</li>
            <li>Mehrdeutigkeiten werden als „Manuelle Prüfung erforderlich“ gekennzeichnet – fehlende Angaben werden nicht erfunden.</li>
            <li>Fehlgeschlagene Analysen können erneut gestartet werden, wenn eine gespeicherte Dokumentversion vorliegt.</li>
            <li>Die Analyse läuft vollständig lokal; es werden keine Vertragsdaten an externe Dienste übertragen.</li>
          </ul>
        </aside>
      </div>
    </div>
  );
}
