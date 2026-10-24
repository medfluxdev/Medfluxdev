"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { EvidenceBbox, SourceNavigationTarget } from "@/lib/contract-detail-types";
import { contentUrl, sourceRegionUrl } from "@/lib/api";
import { resolveEvidenceRect, evidencePrecision } from "@/lib/source-geometry";

const BASE_SCALE = 1.25;
const ZOOM_STEP = 0.25;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const THUMB_WIDTH = 110;
const THUMB_STEP = 6;
type FitMode = "width" | "page" | "actual";

const toolIcon = (body: JSX.Element) => <svg className="pdf-tool-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{body}</svg>;
const TOOL_ICON = {
  pages: toolIcon(<path d="M8 6h13M8 12h13M8 18h13M3 6h.5M3 12h.5M3 18h.5" />),
  search: toolIcon(<path d="M11 4a7 7 0 1 1 0 14a7 7 0 1 1 0-14zM20 20l-4-4" />),
  prev: toolIcon(<path d="m15 6-6 6 6 6" />),
  next: toolIcon(<path d="m9 6 6 6-6 6" />),
  minus: toolIcon(<path d="M5 12h14" />),
  plus: toolIcon(<path d="M12 5v14M5 12h14" />),
  expand: toolIcon(<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" />),
  collapse: toolIcon(<path d="m11 17-5-5 5-5M18 17l-5-5 5-5" />),
  chevron: toolIcon(<path d="m6 9 6 6 6-6" />),
  fit: toolIcon(<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />),
};

interface Props {
  contractId: string;
  orgSlug: string;
  documentVersionId: string | null;
  active: boolean;
  navTarget: SourceNavigationTarget | null;
  /** Meldet die angezeigte Seite (z. B. für „Angabe aus dem Text übernehmen“). */
  onPageChange?: (page: number) => void;
  /** Seitenleiste mit Vorschaubildern anfangs offen (in schmalen Spalten wie „Nachweise“ geschlossen). */
  pagesOpen?: boolean;
  /** Nummerierte Marken der Nachweise auf der Seite (gleiche Nummern wie die Liste); Klick wählt den Nachweis. */
  markers?: PageMarker[];
  onMarker?: (id: string) => void;
  /** „review“: schlanke Leiste (Seite, Zoom, Ganze Seite) und Rahmen statt Marken – für „Nachweise prüfen“. */
  variant?: "full" | "review";
}

export interface PageMarker {
  id: string;
  number: number;
  label: string;
  page: number;
  bbox: EvidenceBbox;
  bbox_space: "pdf_points" | "normalized";
  active: boolean;
  /** Lage nicht im Text belegt: Rahmen gestrichelt in Warnfarbe. */
  approx?: boolean;
}

type LoadStatus = "idle" | "loading" | "ready" | "error";

/** Farbe aus den Design-Tokens für das Zeichnen auf der Leinwand (Hell/Dunkel). */
function cssColor(token: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim() || fallback;
}
type PdfJsModule = typeof import("pdfjs-dist");
type PdfDoc = Awaited<ReturnType<PdfJsModule["getDocument"]>["promise"]>;

function sourceErrorMessage(status: number | null, aborted: boolean): string {
  if (aborted) return "Das Quelldokument hat nicht rechtzeitig geantwortet.";
  if (status === 403) return "Sie haben keine Berechtigung für dieses Quelldokument.";
  if (status === 404) return "Das Quelldokument oder diese Dokumentversion wurde nicht gefunden.";
  if (status != null && status >= 500) return "Das Quelldokument ist serverseitig momentan nicht verfügbar.";
  return "Quelle konnte nicht geladen werden.";
}

export default function PdfViewer({ contractId, orgSlug, documentVersionId, active, navTarget, onPageChange, pagesOpen = true, markers = [], onMarker, variant = "full" }: Props) {
  const review = variant === "review";
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [errorText, setErrorText] = useState("Quelle konnte nicht geladen werden.");
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [dims, setDims] = useState<{ width: number; height: number } | null>(null);
  // Seitengröße in Pixeln, sobald der Maßstab feststeht (vor dem Zeichnen) – für die Nachweis-Marken.
  const [pageBox, setPageBox] = useState<{ width: number; height: number } | null>(null);
  const [retrySeq, setRetrySeq] = useState(0);
  const [refined, setRefined] = useState<{
    key: string;
    status: string;
    bbox: EvidenceBbox | null;
    bbox_space: "pdf_points" | "normalized";
  } | null>(null);
  const pdfRef = useRef<PdfJsModule | null>(null);
  const docRef = useRef<PdfDoc | null>(null);
  const renderTaskRef = useRef<{ cancel: () => void } | null>(null);
  const pageCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const requestSeq = useRef(0);
  const rootRef = useRef<HTMLElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  // Seitenleiste mit Vorschaubildern, Suche im Text, Vollbild.
  const [showPages, setShowPages] = useState(pagesOpen && variant !== "review");
  const [thumbCount, setThumbCount] = useState(THUMB_STEP);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchHits, setSearchHits] = useState<number[] | null>(null);
  const [hitIndex, setHitIndex] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const renderSeq = useRef(0);
  const canRender = status === "ready";

  useEffect(() => {
    if (status === "ready") onPageChange?.(pageNumber);
  }, [status, pageNumber, onPageChange]);

  useEffect(() => {
    if (!active || !documentVersionId) {
      setStatus("idle");
      return;
    }
    let cancelled = false;
    let timedOut = false;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 30000);
    setStatus("loading");
    setErrorText("Quelle konnte nicht geladen werden.");
    setDims(null);
    setPageBox(null);
    const seq = ++requestSeq.current;
    // Never reuse geometry or an old page count across document versions.
    setRefined(null);
    setPageCount(0);

    (async () => {
      let responseStatus: number | null = null;
      try {
        if (docRef.current) {
          void docRef.current.destroy();
          docRef.current = null;
        }
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdfjs/pdf.worker.min.js";
        const res = await fetch(contentUrl(contractId, documentVersionId, orgSlug), {
          signal: controller.signal,
          credentials: "include",
        });
        responseStatus = res.status;
        if (!res.ok) throw new Error(`content ${res.status}`);
        const data = await res.arrayBuffer();
        const doc = await pdfjs.getDocument({ data }).promise;
        if (cancelled || seq !== requestSeq.current) {
          void doc.destroy();
          return;
        }
        pdfRef.current = pdfjs;
        docRef.current = doc;
        setPageCount(doc.numPages);
        const requestedPage = navTarget?.document_version_id === documentVersionId ? navTarget.page : null;
        setPageNumber(requestedPage ? Math.min(Math.max(1, requestedPage), doc.numPages) : 1);
        setStatus("ready");
      } catch (error) {
        if (!cancelled) {
          const aborted = timedOut || (error instanceof DOMException && error.name === "AbortError");
          setErrorText(sourceErrorMessage(responseStatus, aborted));
          setStatus("error");
        }
      } finally {
        clearTimeout(timer);
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
      renderSeq.current += 1;
      renderTaskRef.current?.cancel();
    };
  }, [active, documentVersionId, contractId, orgSlug, retrySeq]);

  useEffect(() => () => {
    renderTaskRef.current?.cancel();
    if (docRef.current) void docRef.current.destroy();
  }, []);

  // Neues Dokument: Suche und Vorschau zurücksetzen.
  useEffect(() => { setSearchHits(null); setQuery(""); setThumbCount(THUMB_STEP); }, [documentVersionId]);

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === rootRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  function toggleFullscreen() {
    if (document.fullscreenElement) void document.exitFullscreen?.();
    else void rootRef.current?.requestFullscreen?.();
  }

  /** Seiten mit dem Suchbegriff (Text der PDF-Seiten, ohne Groß-/Kleinschreibung); springt zum ersten Treffer. */
  async function search() {
    const doc = docRef.current;
    const needle = query.trim().toLocaleLowerCase("de-DE");
    if (!doc || !needle) { setSearchHits(null); return; }
    setSearching(true);
    const hits: number[] = [];
    try {
      for (let page = 1; page <= doc.numPages; page += 1) {
        const content = await (await doc.getPage(page)).getTextContent();
        const text = content.items.map((item) => ("str" in item ? item.str : "")).join(" ").replace(/\s+/g, " ").toLocaleLowerCase("de-DE");
        if (text.includes(needle)) hits.push(page);
      }
    } catch {
      // Ohne Textebene (z. B. Scan ohne Texterkennung) gibt es keine Treffer.
    } finally {
      setSearching(false);
    }
    setSearchHits(hits);
    setHitIndex(0);
    if (hits.length) setPageNumber(hits[0]);
  }

  function jumpHit(step: number) {
    if (!searchHits?.length) return;
    const next = (hitIndex + step + searchHits.length) % searchHits.length;
    setHitIndex(next);
    setPageNumber(searchHits[next]);
  }

  /** Größe an den sichtbaren Bereich anpassen (Seitenbreite, ganze Seite) oder 100 %. */
  async function fit(mode: FitMode) {
    if (mode === "actual") { setZoom(1); return; }
    const doc = docRef.current;
    const stage = stageRef.current;
    if (!doc || !stage) return;
    try {
      const base = (await doc.getPage(pageNumber)).getViewport({ scale: BASE_SCALE });
      const byWidth = (stage.clientWidth - 32) / base.width;
      const byHeight = (stage.clientHeight - 32) / base.height;
      const next = mode === "width" ? byWidth : Math.min(byWidth, byHeight);
      if (Number.isFinite(next) && next > 0) setZoom(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, next)));
    } catch {
      // Ohne Maße bleibt die aktuelle Größe.
    }
  }

  const renderPage = useCallback(async () => {
    const seq = ++renderSeq.current;
    const pdfjs = pdfRef.current;
    const doc = docRef.current;
    const canvas = pageCanvasRef.current;
    if (!pdfjs || !doc || !canvas) return;
    setDims(null);
    // Cancel the previous render before awaiting the next page. An old
    // getPage() completion must never paint over the newly selected page.
    renderTaskRef.current?.cancel();
    renderTaskRef.current = null;
    let page;
    try {
      page = await doc.getPage(pageNumber);
    } catch {
      if (seq === renderSeq.current) {
        setErrorText("Diese PDF-Seite konnte nicht geladen werden.");
        setStatus("error");
      }
      return;
    }
    if (seq !== renderSeq.current || doc !== docRef.current || canvas !== pageCanvasRef.current) return;
    const scale = BASE_SCALE * zoom;
    const viewport = page.getViewport({ scale });
    setPageBox({ width: Math.floor(viewport.width), height: Math.floor(viewport.height) });
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = `${canvas.width}px`;
    canvas.style.height = `${canvas.height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const task = page.render({ canvasContext: ctx, viewport });
    renderTaskRef.current = task;
    try {
      await task.promise;
    } catch (error) {
      if (seq === renderSeq.current && !(error instanceof Error && error.name === "RenderingCancelledException")) {
        setErrorText("Diese PDF-Seite konnte nicht dargestellt werden.");
        setStatus("error");
      }
      return;
    } finally {
      if (renderTaskRef.current === task) renderTaskRef.current = null;
    }
    if (seq !== renderSeq.current || doc !== docRef.current) return;
    setDims({ width: canvas.width, height: canvas.height });
  }, [pageNumber, zoom]);

  useEffect(() => {
    if (status !== "ready") return;
    void renderPage();
  }, [status, renderPage]);

  // Navigate when the selected evidence changes, not on every manual page turn.
  // Including pageNumber here previously forced the reader back to the cited page.
  useEffect(() => {
    if (
      status !== "ready" || pageCount < 1 || !navTarget ||
      navTarget.document_version_id !== documentVersionId ||
      navTarget.page == null
    ) return;
    setPageNumber(Math.min(Math.max(1, navTarget.page), pageCount));
  }, [navTarget, status, documentVersionId, pageCount]);

  useEffect(() => {
    if (
      status !== "ready" || !documentVersionId || !navTarget ||
      !navTarget.label || navTarget.page == null
    ) return;
    if (navTarget.document_version_id !== documentVersionId) return;
    const key = `${orgSlug}|${navTarget.document_version_id}|${navTarget.page}|${navTarget.label}`;
    setRefined(null);
    let cancelled = false;
    const controller = new AbortController();
    (async () => {
      try {
        const res = await fetch(
          sourceRegionUrl(documentVersionId, orgSlug, navTarget.label, navTarget.page ?? null),
          { credentials: "include", signal: controller.signal }
        );
        if (!res.ok) return;
        const body = (await res.json()) as {
          status?: string;
          bbox?: number[] | null;
          bbox_space?: string;
          page?: number | null;
        };
        if (cancelled) return;
        if (body.status === "exact" && Array.isArray(body.bbox) && body.bbox.length === 4 && body.page === navTarget.page) {
          setRefined({
            key,
            status: body.status,
            bbox: { x0: body.bbox[0], y0: body.bbox[1], x1: body.bbox[2], y1: body.bbox[3] },
            bbox_space: body.bbox_space === "normalized" ? "normalized" : "pdf_points",
          });
        }
      } catch {
        // Existing coarse evidence remains available when refinement fails.
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [status, documentVersionId, navTarget, orgSlug]);

  useEffect(() => {
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;
    // Clear the previous page's overlay even when no evidence is selected.
    // Canvas dimensions must follow the currently rendered page before drawing.
    canvas.width = dims?.width ?? 0;
    canvas.height = dims?.height ?? 0;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (review || !navTarget || !dims || navTarget.document_version_id !== documentVersionId || navTarget.page !== pageNumber) return;
    const refinedKey = `${orgSlug}|${navTarget.document_version_id}|${navTarget.page}|${navTarget.label}`;
    const useRefined = refined !== null && refined.key === refinedKey && refined.status === "exact" && refined.bbox !== null;
    const bbox = useRefined ? refined.bbox! : (navTarget.supports_exact_navigation ? navTarget.bbox : null);
    const bboxSpace = useRefined ? refined.bbox_space : navTarget.bbox_space;
    if (!bbox) return;
    const rect = resolveEvidenceRect(bbox, bboxSpace, BASE_SCALE * zoom, dims);
    if (!rect) return;
    const pagePoints = { width: dims.width / (BASE_SCALE * zoom), height: dims.height / (BASE_SCALE * zoom) };
    const precision = evidencePrecision(bbox, bboxSpace, pagePoints);
    // Belegte Fundstelle (Wortlaut in der Box): grün hinterlegt, wie „Bestätigt“.
    if (navTarget.verified || (useRefined && precision !== "coarse")) {
      const success = cssColor("--color-success", "rgb(11, 107, 87)");
      const pad = 6;
      const box = { x: rect.x - pad, y: rect.y - pad, w: rect.width + pad * 2, h: rect.height + pad * 2 };
      const outline = () => {
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") ctx.roundRect(box.x, box.y, box.w, box.h, 8);
        else ctx.rect(box.x, box.y, box.w, box.h);
      };
      ctx.save();
      ctx.globalAlpha = 0.1;
      ctx.fillStyle = success;
      outline();
      ctx.fill();
      ctx.restore();
      ctx.strokeStyle = success;
      ctx.lineWidth = 2;
      outline();
      ctx.stroke();
      return;
    }
    {
      ctx.fillStyle = "rgba(255, 200, 0, 0.12)";
      ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
      ctx.strokeStyle = "#d97706";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([8, 6]);
      ctx.strokeRect(rect.x + 2, rect.y + 2, Math.max(0, rect.width - 4), Math.max(0, rect.height - 4));
      ctx.setLineDash([]);
      ctx.font = "12px sans-serif";
      ctx.fillStyle = "#92400e";
      ctx.fillText("ungefähre Lage (Seitenbereich)", rect.x + 2, rect.y > 16 ? rect.y - 4 : rect.y + rect.height + 14);
      return;
    }
  }, [navTarget, dims, documentVersionId, pageNumber, zoom, refined, orgSlug, review]);

  // Prüfmodus: den aktuellen Rahmen in den sichtbaren Bereich holen (beim Wechsel des Nachweises oder der Größe).
  const currentMarker = review ? markers.find((marker) => marker.active && marker.page === pageNumber)?.id ?? null : null;
  useEffect(() => {
    if (!currentMarker || !pageBox) return;
    const frame = stageRef.current?.querySelector<HTMLElement>(".pdf-frame.is-current");
    const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!frame) return;
    // Nur die Ansicht des Originals scrollen – nicht die ganze Seite (scrollIntoView würde auch die Seite verschieben).
    let box: HTMLElement | null = frame.parentElement;
    while (box && !(box.scrollHeight > box.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(box).overflowY))) box = box.parentElement;
    if (!box || box === document.body || box === document.documentElement) return;
    const f = frame.getBoundingClientRect();
    const b = box.getBoundingClientRect();
    box.scrollTo?.({ top: box.scrollTop + (f.top - b.top) - (box.clientHeight - f.height) / 2, behavior: reduce ? "auto" : "smooth" });
  }, [currentMarker, pageBox]);

  if (!active || !documentVersionId) {
    return <div className="pdf-viewer pdf-idle" role="region" aria-label="Quellansicht"><p className="pdf-placeholder">Wählen Sie oben ein Quelldokument aus, um die Quelle zu öffnen.</p></div>;
  }

  const hitNow = searchHits && searchHits.length ? searchHits[hitIndex] : null;
  return (
    <section className={`pdf-viewer${review ? " pdf-viewer--review" : ""}`} aria-label="Quellansicht (PDF)" ref={rootRef}>
      <div className="pdf-controls" role="toolbar" aria-label="PDF-Ansicht steuern">
        <button type="button" className="pdf-tool" aria-pressed={showPages} onClick={() => setShowPages((open) => !open)}>{TOOL_ICON.pages}Seiten</button>
        <form className="pdf-search" role="search" onSubmit={(event) => { event.preventDefault(); void search(); }}>
          {TOOL_ICON.search}
          <label className="visually-hidden" htmlFor={`pdf-search-${documentVersionId}`}>Im Dokument suchen</label>
          <input id={`pdf-search-${documentVersionId}`} type="search" placeholder="Im Dokument suchen" value={query} disabled={!canRender}
            onChange={(event) => { setQuery(event.target.value); setSearchHits(null); }} />
          {searchHits ? <span className="pdf-search-result" aria-live="polite">
            {searchHits.length === 0 ? "Kein Treffer" : <>
              <button type="button" aria-label="Vorheriger Treffer" disabled={searchHits.length < 2} onClick={() => jumpHit(-1)}>‹</button>
              {hitIndex + 1}/{searchHits.length} · S. {hitNow}
              <button type="button" aria-label="Nächster Treffer" disabled={searchHits.length < 2} onClick={() => jumpHit(1)}>›</button>
            </>}
          </span> : searching ? <span className="pdf-search-result" role="status">Suche …</span> : null}
        </form>
        <span className="pdf-tool-group">
          <button type="button" className="pdf-icon-btn" aria-label="Vorherige Seite" disabled={!canRender || pageNumber <= 1} onClick={() => setPageNumber((p) => Math.max(1, p - 1))}>{TOOL_ICON.prev}</button>
          <span className="page-indicator" aria-live="polite"><span className="visually-hidden">Seite </span>{pageNumber} / {pageCount}</span>
          <button type="button" className="pdf-icon-btn" aria-label="Nächste Seite" disabled={!canRender || pageNumber >= pageCount} onClick={() => setPageNumber((p) => Math.min(pageCount, p + 1))}>{TOOL_ICON.next}</button>
        </span>
        <span className="pdf-tool-group">
          <button type="button" className="pdf-icon-btn" aria-label="Zoom verkleinern" disabled={!canRender} onClick={() => setZoom((z) => Math.max(ZOOM_MIN, z - ZOOM_STEP))}>{TOOL_ICON.minus}</button>
          <button type="button" className="zoom-value" aria-label="Zoom zurücksetzen" disabled={!canRender} onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</button>
          <button type="button" className="pdf-icon-btn" aria-label="Zoom vergrößern" disabled={!canRender} onClick={() => setZoom((z) => Math.min(ZOOM_MAX, z + ZOOM_STEP))}>{TOOL_ICON.plus}</button>
        </span>
        <label className="pdf-fit"><span className="visually-hidden">Größe anpassen</span>
          <select value="" disabled={!canRender} onChange={(event) => { const mode = event.target.value as FitMode; if (mode) void fit(mode); }}>
            <option value="">Anpassen</option>
            <option value="width">Seitenbreite</option>
            <option value="page">Ganze Seite</option>
            <option value="actual">100 %</option>
          </select>
        </label>
        <button type="button" className="pdf-tool pdf-fullscreen" onClick={toggleFullscreen}>{TOOL_ICON.expand}{fullscreen ? "Vollbild beenden" : "Vollbild"}</button>
      </div>
      {status === "loading" && <p className="pdf-status" role="status">Quelle wird geladen…</p>}
      {status === "error" && (
        <div className="pdf-status pdf-error" role="alert">
          <strong>Quelldokument nicht verfügbar</strong>
          <span>{errorText}</span>
          <button type="button" className="btn-link" onClick={() => setRetrySeq((n) => n + 1)}>Erneut laden</button>
        </div>
      )}
      {canRender && <div className={`pdf-body${showPages ? " has-pages" : ""}`}>
        {showPages ? <nav className="pdf-thumbs" aria-label="Seiten">
          <button type="button" className="pdf-thumbs-close" aria-label="Seitenleiste schließen" onClick={() => setShowPages(false)}>{TOOL_ICON.collapse}</button>
          <ol>{Array.from({ length: Math.min(thumbCount, pageCount) }, (_, index) => index + 1).map((page) => <li key={page}>
            <button type="button" className={page === pageNumber ? "is-current" : undefined} aria-current={page === pageNumber ? "page" : undefined} aria-label={`Seite ${page}`} onClick={() => setPageNumber(page)}>
              <PageThumb docRef={docRef} page={page} version={documentVersionId} />
              <span className="pdf-thumb-number" aria-hidden="true">{page}</span>
            </button>
          </li>)}</ol>
          {thumbCount < pageCount ? <button type="button" className="btn btn-sm pdf-thumbs-more" onClick={() => setThumbCount((count) => count + THUMB_STEP)}>Weitere Seiten{TOOL_ICON.chevron}</button> : null}
        </nav> : null}
        <div className="pdf-stage" ref={stageRef}><div className="pdf-page-wrap" style={{ width: dims?.width ?? pageBox?.width }}><canvas ref={pageCanvasRef} className="pdf-page-canvas" /><canvas ref={overlayCanvasRef} className="pdf-overlay-canvas" aria-hidden="true" />
          {pageBox ? markers.filter((marker) => marker.page === pageNumber).map((marker) => {
            const rect = resolveEvidenceRect(marker.bbox, marker.bbox_space, BASE_SCALE * zoom, pageBox);
            if (!rect) return null;
            // Prüfmodus: der aktuelle Nachweis mit Rahmen und Nummer, die übrigen der Seite nur gestrichelt (ohne Nummer).
            const pad = marker.active ? 6 : 2;
            if (review) return <div key={marker.id} className={`pdf-frame${marker.active ? " is-current" : ""}${marker.approx ? " is-approx" : ""}`}
              style={{ left: rect.x - pad, top: rect.y - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }} aria-hidden="true">
              {marker.active ? <span className="pdf-frame-number">{marker.number}</span> : null}
            </div>;
            return <button key={marker.id} type="button" className={`pdf-marker${marker.active ? " is-active" : ""}`} style={{ left: Math.max(0, rect.x - 12), top: Math.max(0, rect.y - 12) }}
              aria-label={`Nachweis ${marker.number}: ${marker.label}`} aria-pressed={marker.active} onClick={() => onMarker?.(marker.id)}>{marker.number}</button>;
          }) : null}</div></div>
      </div>}
      {!review && navTarget && navTarget.document_version_id === documentVersionId && pageNumber === navTarget.page && navTarget.page != null && (
        <p className="pdf-nav-info" aria-live="polite">
          {refined?.key === `${orgSlug}|${navTarget.document_version_id}|${navTarget.page}|${navTarget.label}` && refined.status === "exact" && refined.bbox
            ? `Quelle im Original lokalisiert: ${navTarget.label}`
            : navTarget.verified && navTarget.bbox
              ? `Quelle im Original markiert (Seite ${navTarget.page})`
            : navTarget.supports_exact_navigation && navTarget.bbox
              ? `Quelle: ${navTarget.label} · ungefähre Lage auf Seite ${navTarget.page} (keine exakte Position)`
              : `Quelle: ${navTarget.label} (ohne exakte Position)`}
        </p>
      )}
    </section>
  );
}

/** Vorschaubild einer Seite (klein gerendert, einmal je Dokument und Seite). */
function PageThumb({ docRef, page, version }: { docRef: { current: PdfDoc | null }; page: number; version: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    let cancelled = false;
    let task: { cancel: () => void; promise: Promise<unknown> } | null = null;
    (async () => {
      const doc = docRef.current;
      const canvas = canvasRef.current;
      if (!doc || !canvas) return;
      try {
        const pdfPage = await doc.getPage(page);
        if (cancelled) return;
        const base = pdfPage.getViewport({ scale: 1 });
        const viewport = pdfPage.getViewport({ scale: THUMB_WIDTH / base.width });
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        task = pdfPage.render({ canvasContext: ctx, viewport }) as unknown as { cancel: () => void; promise: Promise<unknown> };
        await task.promise;
      } catch {
        // Vorschau ist nur Komfort; die Seite selbst bleibt erreichbar.
      }
    })();
    return () => { cancelled = true; task?.cancel(); };
  }, [docRef, page, version]);
  return <canvas ref={canvasRef} className="pdf-thumb-canvas" aria-hidden="true" />;
}
