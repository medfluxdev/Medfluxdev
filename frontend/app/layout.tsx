import type { Metadata } from "next";
import ClientNav from "@/components/ClientNav";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { ToastProvider } from "@/components/ui/Toast";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/source-serif-4";
import "./styles/tokens.css";
import "./styles/base.css";
import "./globals.css";
import "./reference-theme.css";
import "./dashboard-reference.css";
import "./contract-workspace.css";
import "./contract-workspace-enhancements.css";
import "./contract-register.css";
import "./auth.css";
import "./profile.css";
import "./organization.css";
import "./ownership.css";
import "./design-system.css";
import "./contracts-list.css";
import "./import-enhancements.css";
import "./work-queue.css";
import "./operational-workflows.css";
import "./release-gate.css";
import "./brand-identity.css";
import "./assistant.css";
import "./master-data.css";
import "./help.css";
import "./styles/components.css";
import "./styles/shell.css";

export const metadata: Metadata = {
  title: {
    default: "MedFlux",
    template: "%s · MedFlux",
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
            <ClientNav>{children}</ClientNav>
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
