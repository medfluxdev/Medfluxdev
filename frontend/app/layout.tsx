import type { Metadata } from "next";
import ClientNav from "@/components/ClientNav";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Medflux",
    template: "%s · Medflux",
  },
  description:
    "Lokales KI-System für deutsche Krankenhäuser zur Analyse und Überwachung von Wartungs- und Serviceverträgen.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <body>
        <a className="skip-link" href="#main-content">
          Zum Hauptinhalt springen
        </a>
        <ToastProvider>
          <ClientNav>
            <div id="main-content" className="skip-target" tabIndex={-1} />
            {children}
          </ClientNav>
        </ToastProvider>
      </body>
    </html>
  );
}