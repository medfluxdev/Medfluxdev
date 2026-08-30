import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Medflux",
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
      <body>{children}</body>
    </html>
  );
}
