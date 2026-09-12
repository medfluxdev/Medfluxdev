import type { Metadata } from "next";
import ClientNav from "@/components/ClientNav";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";
import "./reference-theme.css";
import "./desktop-shell-fix.css";
import "./dashboard-reference.css";
import "./contract-workspace.css";
import "./auth.css";
import "./profile.css";
import "./organization.css";
import "./ownership.css";

export const metadata: Metadata = {
  title: {
    default: "Medflux",
    template: "%s · Medflux",
  },
  description:
    "Lokales KI-System für deutsche Krankenhäuser zur Analyse und Überwachung von Wartungs- und Serviceverträgen.",
};

const ORG_SLUG = process.env.NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <a className="skip-link" href="#main-content">
          Zum Hauptinhalt springen
        </a>
        <ToastProvider>
          <AuthProvider organizationSlug={ORG_SLUG}>
            <ClientNav>
              <div id="main-content" className="skip-target" tabIndex={-1} />
              {children}
            </ClientNav>
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
