interface Props {
  children: React.ReactNode;
}

export default function LoadingState({ children }: Props) {
  return <p className="state-loading">{children}</p>;
}