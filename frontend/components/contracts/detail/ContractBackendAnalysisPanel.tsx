"use client";

import { useEffect, useMemo, useState } from "react";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";
import {
  getAuthorityDiagnostics,
  getContractRiskAnalysis,
  simulateContractTermination,
  type AuthorityDiagnostics,
  type ContractRiskAnalysis,
  type TerminationScenario,
} from "@/lib/domain-api/intelligenceAnalytics";
import { listProcessingJobs, type ProcessingJob } from "@/lib/domain-api/processingJobs";
import InlineAlert from "@/components/ui/InlineAlert";
import LoadingState from "@/components/ui/LoadingState";
import StatusBadge from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/format";

interface Props { data: ContractDetailResponse; organizationSlug: string; }

function evidenceButton(refs: string[] | null | undefined) {
  const clean = (refs ?? []).filter(Boolean);
  if (!clean.length) return null;
  return <button type="button" className="cw-source-button" onClick={() => window.dispatchEvent(new CustomEvent("medflux:intelligence-evidence", { detail: { refs: clean } }))}>Quelle anzeigen</button>;
}

function formatMoney(value: string | number | null | undefined, currency: string | null | undefined) {
  if (value == null) return "Nicht verfügbar";
  const number = Number(value);
  if (!Number.isFinite(number)) return `${value}${currency ? ` ${currency}` : ""}`;
  return currency ? new Intl.NumberFormat("de-DE", { style: "currency", currency, maximumFractionDigits: 2 }).format(number) : new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 }).format(number);
}

function riskTone(level: string | null | undefined): "critical" | "warning" | "success" | "neutral" {
  if (["critical", "high"].includes(level ?? "")) return "critical";
  if (level === "medium") return "warning";
  if (["low", "info"].includes(level ?? "")) return "success";
  return "neutral";
}

function safeLabel(value: string | null | undefined) { return value ? value.replace(/_/g, " ") : "Unbekannt"; }

export default function ContractBackendAnalysisPanel({ data, organizationSlug }: Props) {
  const [risk, setRisk] = useState<ContractRiskAnalysis | null>(null);
  const [authority, setAuthority] = useState<AuthorityDiagnostics | null>(null);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenarioDate, setScenarioDate] = useState("");
  const [scenario, setScenario] = useState<TerminationScenario | null>(null);
  const [scenarioBusy, setScenarioBusy] = useState(false);

  const documents = data.documents ?? [];
  const equipment = data.equipment ?? [];
  const renewalBoundaries = data.dates?.renewal_boundaries ?? [];
  const categoryTotals = data.costs?.category_totals ?? [];
  const priceDevelopment = data.costs?.price_development ?? [];
  const costNotes = data.costs?.notes ?? [];
  const includedServices = data.scope?.included_services ?? [];
  const excludedServices = data.scope?.excluded_services ?? [];
  const tax = data.costs?.tax_breakdown;
  const documentIds = useMemo(() => new Set(documents.map((item) => item.document_version_id)), [documents]);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    Promise.all([getContractRiskAnalysis(organizationSlug, data.contract_id), getAuthorityDiagnostics(organizationSlug, data.contract_id), listProcessingJobs(organizationSlug, { limit: 500 })])
      .then(([riskResult, authorityResult, jobsResult]) => {
        if (!active) return;
        setRisk(riskResult); setAuthority(authorityResult);
        setJobs((jobsResult.items ?? []).filter((job) => documentIds.has(job.document_version_id)));
      })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : "Backend-Analyse konnte nicht vollständig geladen werden."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [data.contract_id, documentIds, organizationSlug]);

  async function runScenario() {
    if (!scenarioDate) return;
    setScenarioBusy(true); setError(null);
    try { setScenario(await simulateContractTermination(organizationSlug, data.contract_id, scenarioDate)); }
    catch (err) { setError(err instanceof Error ? err.message : "Szenario konnte nicht berechnet werden."); }
    finally { setScenarioBusy(false); }
  }

  // Abschnitte je Vertragstyp (lib/contract-sections.ts): Leistungsumfang/SLA und Geräte nur, wo der Typ sie vorsieht.
  const showServiceFacts = !data.sections || data.sections.scope || data.sections.sla;
  const showEquipmentFacts = !data.sections || data.sections.equipment;
  const hasAdvancedFacts = Boolean(data.dates?.start_condition || data.dates?.days_until_latest_cancellation != null || renewalBoundaries.length || categoryTotals.length || priceDevelopment.length || costNotes.length || (showServiceFacts && Boolean(includedServices.length || excludedServices.length || data.scope?.note_de || data.sla?.sla_notes)) || (showEquipmentFacts && equipment.some((item) => item.coverage_start || item.coverage_end || item.service_scope || (item.review_reasons ?? []).length)));
  const riskReasons = risk?.reasons ?? [];
  const authorityIssues = authority?.issues ?? [];

  return <section className="cw-section" aria-labelledby="backend-analysis-heading">
    <div className="cw-section-head"><div><h2 id="backend-analysis-heading">Backend-Vollanalyse</h2><p>Zusätzliche autoritative Berechnungen, Risikoerklärungen und Analyse-Metadaten aus dem Backend.</p></div></div>
    {loading ? <LoadingState>Backend-Analyse wird geladen…</LoadingState> : null}
    {error ? <InlineAlert tone="warning" role="status">{error}</InlineAlert> : null}

    {!loading ? <div className="cw-two-col">
      <section className="card card-pad"><h3>Erklärbares Risiko</h3>{risk ? <><div className="badge-row"><StatusBadge label={`Analyse: ${safeLabel(risk.level)}`} tone={riskTone(risk.level)} />{risk.projected_risk_level ? <StatusBadge label={`Vertragsprojektion: ${safeLabel(risk.projected_risk_level)}`} tone={riskTone(risk.projected_risk_level)} /> : null}<StatusBadge label={`${risk.finding_count ?? riskReasons.length} Gründe`} tone="neutral" /></div>{riskReasons.length ? <ul className="cw-task-list">{riskReasons.map((reason) => <li className="cw-task" key={reason.key}><span className={`cw-priority cw-priority-${reason.severity}`}>{safeLabel(reason.severity)}</span><div><strong>{reason.key.replace(/:/g, " · ")}</strong><p>{reason.explanation}</p>{evidenceButton(reason.evidence_refs)}</div></li>)}</ul> : <p className="cw-muted">Keine expliziten Risiko-Findings vorhanden.</p>}</> : <p className="cw-muted">Keine Risikoanalyse verfügbar.</p>}</section>
      <section className="card card-pad"><h3>Vertragsautorität & Konflikte</h3>{authority ? <><div className="cw-mini-stats"><div><strong>{authority.relation_count ?? 0}</strong><span>Beziehungen</span></div><div><strong>{authority.issue_count ?? authorityIssues.length}</strong><span>Konflikte</span></div></div>{authorityIssues.length ? <ul>{authorityIssues.map((item, index) => <li key={`${item.kind}-${index}`}><strong>{safeLabel(item.kind)}</strong>: {item.message} {evidenceButton(item.evidence_refs)}</li>)}</ul> : <p className="cw-muted">Keine Autoritätskonflikte erkannt.</p>}</> : <p className="cw-muted">Keine Autoritätsdiagnose verfügbar.</p>}</section>
    </div> : null}

    <section className="card card-pad"><h3>Was-wäre-wenn: Kündigung</h3><p className="cw-muted">Die Berechnung kommt vollständig aus dem deterministischen Backend und verwendet nur akzeptierte Jahreskosten und Vertragsdaten.</p><div className="form-grid"><label>Kündigungsdatum<input type="date" value={scenarioDate} onChange={(event) => setScenarioDate(event.target.value)} /></label><div><button type="button" className="btn" disabled={!scenarioDate || scenarioBusy} onClick={() => void runScenario()}>{scenarioBusy ? "Berechnet…" : "Szenario berechnen"}</button></div></div>{scenario ? <div className="cw-definition-grid"><div><dt>Berechenbar</dt><dd>{scenario.known ? "Ja" : "Nein"}</dd></div><div><dt>Geschätzte vermiedene Kosten</dt><dd>{scenario.known ? formatMoney(scenario.estimated_avoided_cost, scenario.currency) : "Nicht berechenbar"}</dd></div><div><dt>Vertragsende</dt><dd>{scenario.basis?.contract_end ? formatDate(scenario.basis.contract_end) : "Nicht verfügbar"}</dd></div><div><dt>Verwendete Jahreskosten</dt><dd>{formatMoney(scenario.basis?.annual_cost, scenario.currency)}</dd></div><div><dt>Begründung</dt><dd>{scenario.reason}</dd></div></div> : null}</section>

    {hasAdvancedFacts ? <section className="card card-pad"><h3>Vollständige Vertragsdaten aus dem Backend</h3><div className="cw-two-col"><div><h4>Laufzeit & Verlängerung</h4><dl className="cw-definition-grid"><div><dt>Ereignisbasierter Beginn</dt><dd>{data.dates?.start_condition ?? "–"}</dd></div><div><dt>Bestätigtes Ereignisdatum</dt><dd>{data.dates?.overridden_start_date ? formatDate(data.dates.overridden_start_date) : "–"}</dd></div><div><dt>Tage bis Kündigungsfrist</dt><dd>{data.dates?.days_until_latest_cancellation ?? "–"}</dd></div><div><dt>Status-Erklärung</dt><dd>{data.dates?.current_status_explanation ?? "–"}</dd></div></dl>{renewalBoundaries.length ? <><h4>Verlängerungsgrenzen</h4><ul>{renewalBoundaries.map((item) => <li key={`${item.period_index}-${item.start_date}-${item.end_date}`}><strong>Periode {item.period_index}</strong>: {item.start_date ? formatDate(item.start_date) : "?"} – {item.end_date ? formatDate(item.end_date) : "?"}{item.review_required ? " · Prüfung erforderlich" : ""}{item.explanation ? ` · ${item.explanation}` : ""}</li>)}</ul></> : null}</div><div><h4>Kosten & Steuer</h4>{categoryTotals.length ? <ul>{categoryTotals.map((item) => <li key={item.key}><strong>{item.label}</strong>: {formatMoney(item.amount, item.currency)}{item.status ? ` · ${safeLabel(item.status)}` : ""}{item.explanation ? ` · ${item.explanation}` : ""}</li>)}</ul> : <p className="cw-muted">Keine Kostenkategorien.</p>}{tax?.computed ? <dl className="cw-definition-grid"><div><dt>Monat netto</dt><dd>{formatMoney(tax.monthly_net, tax.currency)}</dd></div><div><dt>Monat brutto</dt><dd>{formatMoney(tax.monthly_gross, tax.currency)}</dd></div><div><dt>Jahr netto</dt><dd>{formatMoney(tax.annual_net, tax.currency)}</dd></div><div><dt>Jahr brutto</dt><dd>{formatMoney(tax.annual_gross, tax.currency)}</dd></div><div><dt>Jährliche Steuer</dt><dd>{formatMoney(tax.annual_tax, tax.currency)}</dd></div></dl> : null}{priceDevelopment.length ? <><h4>Preisentwicklung</h4><ul>{priceDevelopment.map((item) => <li key={item.key}><strong>{item.label}</strong>{item.text ? `: ${item.text}` : ""}{item.period_years != null ? ` · ${item.period_years} Jahre` : ""}{item.evidence_field_ref ? evidenceButton([item.evidence_field_ref]) : null}</li>)}</ul></> : null}{costNotes.length ? <ul>{costNotes.map((note, index) => <li key={`${index}-${note}`}>{note}</li>)}</ul> : null}</div></div>{showServiceFacts || showEquipmentFacts ? <div className="cw-two-col">{showServiceFacts ? <div><h4>Leistungsumfang</h4><strong>Enthalten</strong>{includedServices.length ? <ul>{includedServices.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="cw-muted">Keine zusätzlichen enthaltenen Leistungen.</p>}<strong>Ausgeschlossen</strong>{excludedServices.length ? <ul>{excludedServices.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="cw-muted">Keine expliziten Ausschlüsse.</p>}{data.scope?.note_de ? <p>{data.scope.note_de}</p> : null}{data.sla?.sla_notes ? <p><strong>SLA-Hinweis:</strong> {data.sla.sla_notes}</p> : null}<p><strong>24/7:</strong> {data.sla?.availability_24_7 == null ? "Unbekannt" : data.sla.availability_24_7 ? "Ja" : "Nein"}</p></div> : null}{showEquipmentFacts ? <div><h4>Geräte – vollständige Vertragsbeziehung</h4>{equipment.length ? <ul>{equipment.map((item) => <li key={item.id}><strong>{item.device_name ?? item.model ?? "Gerät"}</strong>{item.system_name ? ` · System ${item.system_name}` : ""}{item.inventory_number ? ` · Inventar ${item.inventory_number}` : ""}<br/><span>{item.coverage_start ? `Abdeckung ab ${formatDate(item.coverage_start)}` : ""}{item.coverage_end ? ` bis ${formatDate(item.coverage_end)}` : ""}</span>{item.service_scope ? <p>{item.service_scope}</p> : null}<small>Identifikation: {safeLabel(item.identification_quality)} · Beziehung: {safeLabel(item.relationship_quality)}</small>{(item.included_services ?? []).length ? <p>Enthalten: {(item.included_services ?? []).join(", ")}</p> : null}{(item.excluded_services ?? []).length ? <p>Ausgeschlossen: {(item.excluded_services ?? []).join(", ")}</p> : null}{(item.review_reasons ?? []).length ? <p>Prüfgründe: {(item.review_reasons ?? []).join(" · ")}</p> : null}{item.field_ref ? evidenceButton([item.field_ref]) : null}</li>)}</ul> : <p className="cw-muted">Keine Geräte.</p>}</div> : null}</div> : null}</section> : null}

    <section className="card card-pad"><h3>Analyse-/Verarbeitungshistorie</h3>{jobs.length === 0 ? <p className="cw-muted">Keine Verarbeitungsläufe zu den Vertragsdokumenten gefunden.</p> : <div className="table-wrap" tabIndex={0}><table className="contract-table"><thead><tr><th>Status</th><th>Provider</th><th>OCR</th><th>Seiten</th><th>Dauer</th><th>Ergebnis</th><th>Zeitpunkt</th></tr></thead><tbody>{jobs.map((job) => { const statusLabel = job.status_label_de ?? safeLabel(job.status); const resultLabel = job.result_label_de ?? (job.message ? job.message : `${job.success_count ?? 0} erfolgreich / ${job.failure_count ?? 0} fehlgeschlagen`); return <tr key={job.id}><td><StatusBadge label={statusLabel} tone={job.status === "succeeded" ? "success" : job.status === "failed" ? "critical" : "neutral"} /></td><td>{job.provider ?? "–"}{job.provider_version ? ` · ${job.provider_version}` : ""}</td><td>{job.ocr_engine ?? (job.do_ocr ? "aktiv" : "–")}</td><td>{job.page_count ?? "–"}</td><td>{job.processing_duration != null ? `${job.processing_duration.toFixed(2)} s` : "–"}</td><td>{resultLabel}</td><td>{job.created_at ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "short" }).format(new Date(job.created_at)) : "–"}</td></tr>; })}</tbody></table></div>}</section>
  </section>;
}
