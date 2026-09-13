interface Props {
  children: React.ReactNode;
}

export default function LoadingState({ children }: Props) {
  return (
    <p className="state-loading" role="status">
      <span className="loading-spinner" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}
