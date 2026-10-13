import { NextResponse, type NextRequest } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const LOOPBACK_ALIASES = new Set(["127.0.0.1", "[::1]"]);

function apiHostname(): string | null {
  try {
    return new URL(API_BASE).hostname;
  } catch {
    return null;
  }
}

/**
 * Wer die App über 127.0.0.1 statt localhost öffnet, landet sonst auf einem anderen
 * Ursprung als die API (localhost:8000): CORS lehnt ab, das Sitzungscookie gilt nicht,
 * die Anmeldung meldet „Verbindung fehlgeschlagen“. Deshalb auf localhost umleiten.
 */
export function middleware(request: NextRequest) {
  // nextUrl trägt im Entwicklungsserver nicht verlässlich den aufgerufenen Host; der Host-Kopf schon.
  const host = request.headers.get("host") ?? "";
  const hostname = host.startsWith("[") ? host.slice(0, host.indexOf("]") + 1) : host.split(":")[0];
  if (apiHostname() !== "localhost" || !LOOPBACK_ALIASES.has(hostname)) return NextResponse.next();
  const url = new URL(`${request.nextUrl.pathname}${request.nextUrl.search}`, `${request.nextUrl.protocol}//${host}`);
  url.hostname = "localhost";
  // Keine 307: Next hält localhost:<port> für den eigenen Ursprung und kürzt Location auf den Pfad,
  // der Browser bliebe auf 127.0.0.1. Refresh lässt Next unverändert.
  const target = url.toString();
  return new NextResponse(`<!doctype html><meta charset="utf-8"><title>Weiterleitung</title><a href="${target}">Weiter zu MedFlux</a>`, {
    status: 200,
    headers: { "Content-Type": "text/html; charset=utf-8", Refresh: `0; url=${target}`, "Cache-Control": "no-store" },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
