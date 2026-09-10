interface Props {
  children: React.ReactNode;
}

export default function EmptyState({ children }: Props) {
  return <p className="state-empty">{children}</p>;
}