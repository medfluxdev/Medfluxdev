"use client";

import dynamic from "next/dynamic";
import Skeleton from "@/components/ui/Skeleton";

// U7: Teile der Vertragsseite, die erst in ihrem Reiter gebraucht werden, laden getrennt.
// pdfjs-dist selbst laedt PdfViewer zusaetzlich erst beim Oeffnen eines Dokuments.
const loading = (label: string) => function LazyLoading() { return <Skeleton lines={4} label={label} />; };

export const PdfViewer = dynamic(() => import("./PdfViewer"), { ssr: false, loading: loading("Dokumentansicht wird geladen…") });
export const ContractIntelligencePanel = dynamic(() => import("./ContractIntelligencePanel"), { loading: loading("Vertragsanalyse wird geladen…") });
export const ContractBackendAnalysisPanel = dynamic(() => import("./ContractBackendAnalysisPanel"), { loading: loading("Analyse wird geladen…") });
export const ContractOwnershipPanel = dynamic(() => import("./ContractOwnershipPanel"), { loading: loading("Verantwortliche werden geladen…") });
export const ContractBillingPanel = dynamic(() => import("./ContractBillingPanel"), { loading: loading("Abrechnung wird geladen…") });
