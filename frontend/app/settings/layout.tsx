import Link from "next/link";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div className="settings-profile-link">
        <Link href="/profile" className="btn">Mein Profil</Link>
      </div>
      {children}
    </>
  );
}
