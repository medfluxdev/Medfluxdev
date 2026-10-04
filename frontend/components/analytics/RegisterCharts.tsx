"use client";

import Link from "next/link";
import { useState } from "react";

// Diagramme nach den Dataviz-Regeln: dünne Balken (<= 24px), 4px gerundete
// Enden an der Basislinie, 2px Flächenabstand, Legende ab zwei Reihen, Text in
// Text-Tokens, Hover-Tooltip je Marke und eine Tabellenansicht.

export type BarDatum = { label: string; value: number; display: string; href?: string; note?: string };

const BAR = 18;
const ROW = 30;

function roundedBar(x: number, y: number, width: number, height: number, horizontal: boolean) {
  const r = Math.min(4, horizontal ? height / 2 : width / 2, horizontal ? width : height);
  if (width <= 0 || height <= 0) return "";
  if (horizontal) {
    return `M${x},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${y + height - r} Q${x + width},${y + height} ${x + width - r},${y + height} H${x} Z`;
  }
  return `M${x},${y + height} V${y + r} Q${x},${y} ${x + r},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${y + height} Z`;
}

function niceMax(value: number) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) if (step * power >= value) return step * power;
  return 10 * power;
}

function Tooltip({ text }: { text: string | null }) {
  return <p className="viz-tooltip" role="status" aria-live="polite">{text ?? " "}</p>;
}

export function HorizontalBarChart({ title, data, valueLabel }: { title: string; data: BarDatum[]; valueLabel: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const labelWidth = 170;
  const plot = 300;
  const valueSpace = 110;
  const max = niceMax(Math.max(0, ...data.map((item) => item.value)));
  const height = data.length * ROW + 8;
  return <figure className="viz">
    <svg viewBox={`0 0 ${labelWidth + plot + valueSpace} ${height}`} role={data.some((item) => item.href) ? "group" : "img"} aria-label={`${title}: ${data.map((item) => `${item.label} ${item.display}`).join(", ")}`}>
      <line x1={labelWidth} x2={labelWidth} y1={0} y2={height} className="viz-axis" />
      {data.map((item, index) => {
        const y = index * ROW + (ROW - BAR) / 2;
        const width = (item.value / max) * plot;
        const bar = <g onMouseEnter={() => setHover(`${item.label}: ${item.display}${item.note ? ` · ${item.note}` : ""}`)} onMouseLeave={() => setHover(null)}>
          <rect x={0} y={index * ROW} width={labelWidth + plot + valueSpace} height={ROW} fill="transparent" />
          <text x={labelWidth - 8} y={y + BAR / 2} dominantBaseline="middle" textAnchor="end" className="viz-label">{item.label.length > 24 ? `${item.label.slice(0, 23)}…` : item.label}</text>
          <path d={roundedBar(labelWidth, y, width, BAR, true)} className="viz-series-1" />
          <text x={labelWidth + width + 6} y={y + BAR / 2} dominantBaseline="middle" className="viz-value">{item.display}</text>
        </g>;
        return item.href ? <a key={item.label} href={item.href} aria-label={`${item.label}: ${item.display} – in der Liste öffnen`}>{bar}</a> : <g key={item.label}>{bar}</g>;
      })}
    </svg>
    <Tooltip text={hover} />
    <details className="viz-table"><summary>Als Tabelle</summary>
      <table className="rg-table"><thead><tr><th scope="col">{title}</th><th scope="col">{valueLabel}</th></tr></thead>
        <tbody>{data.map((item) => <tr key={item.label}><th scope="row">{item.href ? <Link href={item.href}>{item.label}</Link> : item.label}</th><td className="num">{item.display}{item.note ? ` (${item.note})` : ""}</td></tr>)}</tbody></table>
    </details>
  </figure>;
}

export type ColumnSeries = { key: string; label: string; className: string };
export type ColumnDatum = { label: string; sublabel?: string; values: Record<string, number>; display: Record<string, string> };

export function ColumnChart({ title, series, data, stacked = false, format }: {
  title: string; series: ColumnSeries[]; data: ColumnDatum[]; stacked?: boolean; format: (value: number) => string;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const plotHeight = 180;
  const top = 18;
  const axisWidth = 70;
  const band = 64;
  const width = axisWidth + data.length * band + 8;
  const totals = data.map((item) => stacked ? series.reduce((sum, entry) => sum + (item.values[entry.key] ?? 0), 0) : Math.max(...series.map((entry) => item.values[entry.key] ?? 0)));
  const max = niceMax(Math.max(0, ...totals));
  const ticks = [0, 0.5, 1].map((share) => share * max);
  const y = (value: number) => top + plotHeight - (value / max) * plotHeight;
  const barWidth = stacked ? Math.min(24, band - 20) : Math.min(20, (band - 20 - (series.length - 1) * 2) / series.length);

  return <figure className="viz">
    {series.length > 1 ? <ul className="viz-legend">{series.map((entry) => <li key={entry.key}><span className={`viz-swatch ${entry.className}`} aria-hidden="true" />{entry.label}</li>)}</ul> : null}
    <svg viewBox={`0 0 ${width} ${top + plotHeight + 40}`} role="img" aria-label={`${title}: ${data.map((item) => `${item.label} ${series.map((entry) => `${entry.label} ${item.display[entry.key]}`).join(", ")}`).join("; ")}`}>
      {ticks.map((tick) => <g key={tick}>
        <line x1={axisWidth} x2={width} y1={y(tick)} y2={y(tick)} className="viz-grid" />
        <text x={axisWidth - 6} y={y(tick)} textAnchor="end" dominantBaseline="middle" className="viz-tick">{format(tick)}</text>
      </g>)}
      {data.map((item, index) => {
        const x0 = axisWidth + index * band + 10;
        let stackBase = 0;
        const groupWidth = stacked ? barWidth : series.length * barWidth + (series.length - 1) * 2;
        const start = x0 + (band - 20 - groupWidth) / 2;
        return <g key={item.label} onMouseEnter={() => setHover(`${item.label}${item.sublabel ? ` (${item.sublabel})` : ""}: ${series.map((entry) => `${entry.label} ${item.display[entry.key]}`).join(" · ")}`)} onMouseLeave={() => setHover(null)}>
          <rect x={x0 - 10} y={top} width={band} height={plotHeight + 36} fill="transparent" />
          {series.map((entry, position) => {
            const value = item.values[entry.key] ?? 0;
            if (stacked) {
              const isTop = series.slice(position + 1).every((next) => (item.values[next.key] ?? 0) === 0);
              const segmentTop = y(stackBase + value);
              const segmentHeight = Math.max(0, y(stackBase) - segmentTop - (stackBase > 0 ? 2 : 0));
              stackBase += value;
              if (value <= 0) return null;
              return isTop
                ? <path key={entry.key} d={roundedBar(start, segmentTop, barWidth, segmentHeight, false)} className={entry.className} />
                : <rect key={entry.key} x={start} y={segmentTop} width={barWidth} height={segmentHeight} className={entry.className} />;
            }
            const x = start + position * (barWidth + 2);
            return <path key={entry.key} d={roundedBar(x, y(value), barWidth, y(0) - y(value), false)} className={entry.className} />;
          })}
          <text x={x0 + (band - 20) / 2} y={top + plotHeight + 14} textAnchor="middle" className="viz-tick">{item.label}</text>
          {item.sublabel ? <text x={x0 + (band - 20) / 2} y={top + plotHeight + 28} textAnchor="middle" className="viz-tick">{item.sublabel}</text> : null}
        </g>;
      })}
      <line x1={axisWidth} x2={width} y1={y(0)} y2={y(0)} className="viz-axis" />
    </svg>
    <Tooltip text={hover} />
    <details className="viz-table"><summary>Als Tabelle</summary>
      <table className="rg-table"><thead><tr><th scope="col">{title}</th>{series.map((entry) => <th key={entry.key} scope="col">{entry.label}</th>)}</tr></thead>
        <tbody>{data.map((item) => <tr key={item.label}><th scope="row">{item.label}{item.sublabel ? ` (${item.sublabel})` : ""}</th>{series.map((entry) => <td key={entry.key} className="num">{item.display[entry.key]}</td>)}</tr>)}</tbody></table>
    </details>
  </figure>;
}
