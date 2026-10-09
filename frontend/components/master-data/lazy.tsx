"use client";

import dynamic from "next/dynamic";

// Schnellanlage erst laden, wenn sie gebraucht wird (Vertragsseite bleibt im Leistungsbudget).
export const QuickCreatePartner = dynamic(() => import("./QuickCreatePartner"), { ssr: false });
