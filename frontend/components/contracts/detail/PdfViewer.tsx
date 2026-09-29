"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { EvidenceBbox, SourceNavigationTarget } from "@/lib/contract-detail-types";
import { contentUrl, sourceRegionUrl } from "@/lib/api";
import { resolveEvidenceRect, evidencePrecision } from "@/lib/source-geometry";
import PageControls from "./PageControls";

const BASE_SCALE = 1.25;
const ZOOM_STEP = 0.25;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;

interface Props {
  contractId: string;
  orgSlug: string;
  documentVersionId: string | null;
  active: boolean;
  navTarget: SourceNavigationTarget | null;
}

type LoadStatus = "idle" | "loading" | "ready" | "error";
type PdfJsModule = typeof import("pdfjs-dist");
type PdfDoc = Awaited<ReturnType<PdfJsModule["getDocument"]>["promise"]>;

function sourceErrorMessage(status: number | null, aborted: boolean): string {
  if (aborted) return "Das Quelldokument hat nicht rechtzeitig geantwortet.";
  if (status === 403) return "Sie haben keine Berechtigung für dieses Quelldokument.";
  if (status === 404) return "Das Quelldokument oder diese Dokumentversion wurde nicht gefunden.";
  if (status != null && status >= 500) return "Das Quelldokument ist serverseitig momentan nicht verfügbar.";
  return "Quelle konnte nicht geladen werden.";
}

export default function PdfViewer({ contractId, orgSlug, documentVersionId, active, navTarget }: Props) {
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [errorText, setErrorText] = useState("Quelle konnte nicht geladen werden.");
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [dims, setDims] = useState<{ width: number; height: number } | null>(null);
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
  const canRender = status === "ready";

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
      renderTaskRef.current?.cancel();
    };
  }, [active, documentVersionId, contractId, orgSlug, retrySeq]);

  useEffect(() => () => {
    renderTaskRef.current?.cancel();
    if (docRef.current) void docRef.current.destroy();
  }, []);

  const renderPage = useCallback(async () => {
    const pdfjs = pdfRef.current;
    const doc = docRef.current;
    const canvas = pageCanvasRef.current;
    if (!pdfjs || !doc || !canvas) return;
    const page = await doc.getPage(pageNumber);
    const scale = BASE_SCALE * zoom;
    const viewport = page.getViewport({ scale });
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = `${canvas.width}px`;
    canvas.style.height = `${canvas.height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (renderTaskRef.current) renderTaskRef.current.cancel();
    const task = page.render({ canvasContext: ctx, viewport });
    renderTaskRef.current = task;
    try {
      await task.promise;
    } catch {
      return;
    } finally {
      renderTaskRef.current = null;
    }
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
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!navTarget || !dims || navTarget.document_version_id !== documentVersionId || navTarget.page !== pageNumber) return;
    const refinedKey = `${orgSlug}|${navTarget.document_version_id}|${navTarget.page}|${navTarget.label}`;
    const useRefined = refined !== null && refined.key === refinedKey && refined.status === "exact" && refined.bbox !== null;
    const bbox = useRefined ? refined.bbox! : (navTarget.supports_exact_navigation ? navTarget.bbox : null);
    const bboxSpace = useRefined ? refined.bbox_space : navTarget.bbox_space;
    if (!bbox) return;
    canvas.width = dims.width;
    canvas.height = dims.height;
    const rect = resolveEvidenceRect(bbox, bboxSpace, BASE_SCALE * zoom, dims);
    if (!rect) return;
    const pagePoints = { width: dims.width / (BASE_SCALE * zoom), height: dims.height / (BASE_SCALE * zoom) };
    const precision = evidencePrecision(bbox, bboxSpace, pagePoints);
    if (precision === "coarse") {
      ctx.fillStyle = "rgba(255, 200, 0, 0.12)";
      ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
      ctx.strokeStyle = "#d97706";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([8, 6]);
      ctx.strokeRect(rect.x + 2, rect.y + 2, Math.max(0, rect.width - 4), Math.max(0, rect.height - 4));
      ctx.setLineDash([]);
      ctx.font = "12px sans-serif";
      ctx.fillStyle = "#92400e";
      ctx.fillText("ungefähre Lage (Seitenbereich)", rect.x + 6, rect.y + 16);
      return;
    }
    ctx.fillStyle = "rgba(255, 200, 0, 0.25)";
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 2;
    ctx.strokeRect(rect.x + 1, rect.y + 1, Math.max(0, rect.width - 2), Math.max(0, rect.height - 2));
  }, [navTarget, dims, documentVersionId, pageNumber, zoom, refined, orgSlug]);

  if (!active || !documentVersionId) {
    return <div className="pdf-viewer pdf-idle" role="region" aria-label="Quellansicht"><p className="pdf-placeholder">Wählen Sie oben ein Quelldokument aus, um die Quelle zu öffnen.</p></div>;
  }

  return (
    <section className="pdf-viewer" aria-label="Quellansicht (PDF)">
      <PageControls
        pageNumber={pageNumber}
        pageCount={pageCount}
        zoom={zoom}
        canRender={canRender}
        onPrev={() => setPageNumber((p) => Math.max(1, p - 1))}
        onNext={() => setPageNumber((p) => Math.min(pageCount, p + 1))}
        onZoomOut={() => setZoom((z) => Math.max(ZOOM_MIN, z - ZOOM_STEP))}
        onZoomIn={() => setZoom((z) => Math.min(ZOOM_MAX, z + ZOOM_STEP))}
        onResetZoom={() => setZoom(1)}
      />
      {status === "loading" && <p className="pdf-status" role="status">Quelle wird geladen…</p>}
      {status === "error" && (
        <div className="pdf-status pdf-error" role="alert">
          <strong>Quelldokument nicht verfügbar</strong>
          <span>{errorText}</span>
          <button type="button" className="btn-link" onClick={() => setRetrySeq((n) => n + 1)}>Erneut laden</button>
        </div>
      )}
      {canRender && <div className="pdf-stage"><div className="pdf-page-wrap" style={{ width: dims?.width }}><canvas ref={pageCanvasRef} className="pdf-page-canvas" /><canvas ref={overlayCanvasRef} className="pdf-overlay-canvas" aria-hidden="true" /></div></div>}
      {navTarget && navTarget.document_version_id === documentVersionId && pageNumber === navTarget.page && navTarget.page != null && (
        <p className="pdf-nav-info" aria-live="polite">
          {navTarget.supports_exact_navigation && navTarget.bbox && evidencePrecision(
            navTarget.bbox,
            navTarget.bbox_space,
            dims ? { width: dims.width / (BASE_SCALE * zoom), height: dims.height / (BASE_SCALE * zoom) } : undefined
          ) === "exact"
            ? `Quelle (Seitenbereich) hervorgehoben: ${navTarget.label}`
            : navTarget.supports_exact_navigation && navTarget.bbox
              ? `Quelle: ${navTarget.label} · ungefähre Lage auf Seite ${navTarget.page} (keine exakte Position)`
              : `Quelle: ${navTarget.label} (ohne exakte Position)`}
        </p>
      )}
    </section>
  );
}
