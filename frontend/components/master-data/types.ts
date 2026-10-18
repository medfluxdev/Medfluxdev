import type { ReactNode } from "react";
import type { Column } from "@/components/ui/DataTable";
import type { MasterDataImportKind, MasterDataKind } from "@/lib/domain-api/masterData";

export type FormValue = string | boolean | string[];
export type FormValues = Record<string, FormValue>;

export interface FieldOption {
  value: string;
  label: string;
}

export interface FieldDef {
  key: string;
  label: string;
  kind?: "text" | "textarea" | "select" | "search" | "checkbox" | "number" | "checks" | "email" | "url";
  required?: boolean;
  maxLength?: number;
  min?: number;
  max?: number;
  hint?: string;
  /** Leere Auswahl (z. B. "Krankenhausweit"); ohne Angabe ist eine Auswahl Pflicht. */
  emptyOption?: string;
  options?: FieldOption[];
  /** Nur beim Anlegen aenderbar (z. B. Zuordnung zu einem Krankenhaus). */
  createOnly?: boolean;
  /** Ueberschrift, unter der das Feld gruppiert wird. */
  section?: string;
  wide?: boolean;
}

export interface ImportColumn {
  key: string;
  label: string;
  /** Weitere akzeptierte Spaltenueberschriften (klein geschrieben). */
  aliases?: string[];
  required?: boolean;
}

export interface FilterDef<T, C> {
  key: string;
  label: string;
  allLabel: string;
  options: (context: C) => FieldOption[];
  match: (row: T, value: string) => boolean;
}

/** Beschreibt eine Stammdaten-Art fuer Liste, Formular, Import und Export. */
export interface EntityDefinition<T, C> {
  kind: MasterDataKind;
  singular: string;
  plural: string;
  /** Objekttyp im Aktivitaetsprotokoll (Einzelhistorie). */
  objectType: string;
  load: (organizationSlug: string) => Promise<{ rows: T[]; context: C }>;
  /** Nur den Kontext laden (Schnellanlage aus anderen Formularen). */
  loadContext: (organizationSlug: string) => Promise<C>;
  id: (row: T) => string;
  label: (row: T) => string;
  /** Bezeichnung aus dem Formular (fuer Meldungen nach dem Anlegen). */
  formLabel: (form: FormValues) => string;
  active: (row: T) => boolean;
  searchText: (row: T, context: C) => string;
  columns: (context: C) => Column<T>[];
  fields: (context: C, form: FormValues, row: T | null) => FieldDef[];
  emptyForm: (context: C, preset?: FormValues) => FormValues;
  toForm: (row: T, context: C) => FormValues;
  create: (organizationSlug: string, form: FormValues, options: { force: boolean }) => Promise<{ id: string }>;
  update: (organizationSlug: string, row: T, form: FormValues) => Promise<unknown>;
  setActive: (organizationSlug: string, row: T, active: boolean) => Promise<unknown>;
  /** Spalte + Wert der Vertragsliste, um verwendende Vertraege zu zeigen. */
  registerFilter?: (row: T, context: C) => { column: string; value: string; op?: "in" | "contains" } | null;
  /** Überschrift der Zählspalte (Standard „Verträge“), z. B. „Verstöße“ bei Regeln. */
  usageLabel?: string;
  /** Bei Konflikt (409) aehnliche Eintraege suchen und "Trotzdem anlegen" anbieten. */
  findSimilar?: (organizationSlug: string, form: FormValues) => Promise<string[]>;
  filters?: FilterDef<T, C>[];
  importKind?: MasterDataImportKind;
  importColumns?: ImportColumn[];
  exportRow?: (row: T, context: C) => (string | number | null)[];
  exportHeader?: string[];
  /** Hinweistext ueber der Tabelle (z. B. was Deaktivieren bewirkt). */
  intro?: ReactNode;
  /** Inhalt ueber dem Formular beim Bearbeiten (z. B. KI-Vorschlaege aus Vertraegen); `refresh` laedt den Eintrag neu. */
  editorTop?: (row: T, organizationSlug: string, refresh: () => void) => ReactNode;
}

export interface ManagerApi<T> {
  reload: () => Promise<void>;
  openEdit: (row: T) => void;
  openCreate: (preset?: FormValues) => void;
  canEdit: boolean;
}

export function text(form: FormValues, key: string): string {
  const value = form[key];
  return typeof value === "string" ? value.trim() : "";
}

export function optional(form: FormValues, key: string): string | null {
  return text(form, key) || null;
}
