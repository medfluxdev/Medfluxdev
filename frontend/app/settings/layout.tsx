import Link from "next/link";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div style={{ display: "flex", justifyContent: "flex-end", padding: "18px 28px 0" }}>
        <Link
          href="/profile"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            minHeight: 38,
            padding: "8px 13px",
            border: "1px solid #d7e1e8",
            borderRadius: 10,
            background: "#fff",
            color: "#20324d",
            fontSize: 13,
            fontWeight: 800,
            textDecoration: "none",
          }}
        >
          <span aria-hidden="true">👤</span>
          Mein Profil
        </Link>
      </div>
      {children}
    </>
  );
}
