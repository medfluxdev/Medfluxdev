"use client";

import { useId } from "react";
import Field from "@/components/ui/Field";
import type { FieldDef, FormValues } from "./types";

interface Props {
  fields: FieldDef[];
  values: FormValues;
  onChange: (key: string, value: string | boolean | string[]) => void;
  readOnly: boolean;
  editing: boolean;
  errors?: Record<string, string>;
}

// Formular aus Felddefinitionen; Felder mit gleicher `section` stehen zusammen.
export default function EntityForm({ fields, values, onChange, readOnly, editing, errors = {} }: Props) {
  const prefix = useId();
  const sections: { title: string | null; fields: FieldDef[] }[] = [];
  for (const field of fields) {
    const title = field.section ?? null;
    const last = sections[sections.length - 1];
    if (last && last.title === title) last.fields.push(field);
    else sections.push({ title, fields: [field] });
  }

  function control(field: FieldDef) {
    const id = `${prefix}-${field.key}`;
    const disabled = readOnly || (editing && field.createOnly);
    const value = values[field.key];
    const describedBy = errors[field.key] ? `${id}-error` : undefined;
    switch (field.kind) {
      case "checkbox":
        return <label className="md-check" key={field.key}>
          <input id={id} type="checkbox" checked={value === true} disabled={disabled} onChange={(event) => onChange(field.key, event.target.checked)} />
          <span>{field.label}</span>
          {field.hint ? <small className="field-hint">{field.hint}</small> : null}
        </label>;
      case "checks": {
        const selected = Array.isArray(value) ? value : [];
        return <fieldset className="md-checks" key={field.key} disabled={disabled}>
          <legend>{field.label}</legend>
          {(field.options ?? []).length === 0 ? <p className="field-hint">Keine Einträge vorhanden.</p> : null}
          {(field.options ?? []).map((option) => <label key={option.value} className="md-check">
            <input
              type="checkbox"
              checked={selected.includes(option.value)}
              onChange={(event) => onChange(field.key, event.target.checked ? [...selected, option.value] : selected.filter((item) => item !== option.value))}
            />
            <span>{option.label}</span>
          </label>)}
          {field.hint ? <p className="field-hint">{field.hint}</p> : null}
        </fieldset>;
      }
      default: {
        const common = {
          id,
          disabled,
          required: field.required,
          "aria-invalid": errors[field.key] ? true : undefined,
          "aria-describedby": describedBy,
        };
        const input = field.kind === "select"
          ? <select {...common} value={typeof value === "string" ? value : ""} onChange={(event) => onChange(field.key, event.target.value)}>
            {field.emptyOption !== undefined ? <option value="">{field.emptyOption}</option> : <option value="" disabled>Bitte wählen</option>}
            {(field.options ?? []).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          : field.kind === "textarea"
            ? <textarea {...common} rows={3} maxLength={field.maxLength} value={typeof value === "string" ? value : ""} onChange={(event) => onChange(field.key, event.target.value)} />
            : <input
              {...common}
              type={field.kind === "number" ? "number" : field.kind === "email" ? "email" : field.kind === "url" ? "url" : "text"}
              inputMode={field.kind === "number" ? "numeric" : undefined}
              min={field.min}
              max={field.max}
              maxLength={field.maxLength}
              value={typeof value === "string" ? value : ""}
              onChange={(event) => onChange(field.key, event.target.value)}
            />;
        return <div key={field.key} className={field.wide || field.kind === "textarea" ? "md-wide" : undefined}>
          <Field label={`${field.label}${field.required ? " *" : ""}`} htmlFor={id} hint={editing && field.createOnly ? "Kann nach dem Anlegen nicht mehr geändert werden." : field.hint}>
            {input}
          </Field>
          {errors[field.key] ? <span id={`${id}-error`} className="field-error">{errors[field.key]}</span> : null}
        </div>;
      }
    }
  }

  return <div className="md-form">
    {sections.map((section, index) => <section key={`${section.title ?? "main"}-${index}`} className="md-form-section" aria-label={section.title ?? undefined}>
      {section.title ? <h3>{section.title}</h3> : null}
      <div className="form-grid">{section.fields.map(control)}</div>
    </section>)}
  </div>;
}

// Pflichtfelder pruefen, bevor gespeichert wird (das Backend prueft erneut).
export function missingRequired(fields: FieldDef[], values: FormValues, editing: boolean): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    if (!field.required || (editing && field.createOnly)) continue;
    const value = values[field.key];
    if (typeof value === "string" ? !value.trim() : Array.isArray(value) ? value.length === 0 : !value) {
      errors[field.key] = `${field.label} ist erforderlich.`;
    }
  }
  return errors;
}
