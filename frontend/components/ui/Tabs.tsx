"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";

export interface TabItem<K extends string> {
  key: K;
  label: ReactNode;
  badge?: ReactNode;
}

interface Props<K extends string> {
  label: string;
  items: TabItem<K>[];
  active: K;
  onChange: (key: K) => void;
  idPrefix?: string;
}

// Barrierearme Reiter: Pfeiltasten, Pos1/Ende, nur aktiver Reiter im Tab-Fluss.
export default function Tabs<K extends string>({ label, items, active, onChange, idPrefix = "tab" }: Props<K>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function move(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = items.length - 1;
    const next = event.key === "ArrowRight" ? (index === last ? 0 : index + 1)
      : event.key === "ArrowLeft" ? (index === 0 ? last : index - 1)
      : event.key === "Home" ? 0 : event.key === "End" ? last : -1;
    if (next < 0) return;
    event.preventDefault();
    refs.current[next]?.focus();
    onChange(items[next].key);
  }

  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item, index) => (
        <button
          key={item.key}
          ref={(node) => { refs.current[index] = node; }}
          id={`${idPrefix}-${item.key}`}
          type="button"
          role="tab"
          aria-selected={item.key === active}
          aria-controls={`${idPrefix}-panel`}
          tabIndex={item.key === active ? 0 : -1}
          onClick={() => onChange(item.key)}
          onKeyDown={(event) => move(event, index)}
        >
          {item.label}
          {item.badge != null ? <span className="badge">{item.badge}</span> : null}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ idPrefix = "tab", active, children }: { idPrefix?: string; active: string; children: ReactNode }) {
  return <div id={`${idPrefix}-panel`} role="tabpanel" aria-labelledby={`${idPrefix}-${active}`} tabIndex={0} className="tab-panel">{children}</div>;
}
