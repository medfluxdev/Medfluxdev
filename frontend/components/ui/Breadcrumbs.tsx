import Link from "next/link";

export interface Crumb {
  label: string;
  href?: string;
}

export default function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav className="breadcrumbs" aria-label="Brotkrümelnavigation">
      <ol>
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return <li key={`${item.label}-${index}`}>{item.href && !last ? <Link href={item.href}>{item.label}</Link> : <span aria-current={last ? "page" : undefined}>{item.label}</span>}</li>;
        })}
      </ol>
    </nav>
  );
}
