export interface ActionLike {
  title_de: string;
  target_date: string | null;
}

function normalizedTitle(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase("de-DE").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

/** Remove a warning only when the visible task is the same titled issue/date. */
export function removeWarningsRepresentedByTasks<T extends ActionLike>(
  tasks: readonly ActionLike[],
  warnings: readonly T[],
): T[] {
  const taskKeys = new Set(tasks.map((item) => `${normalizedTitle(item.title_de)}|${item.target_date ?? ""}`));
  const seen = new Set<string>();
  return warnings.filter((warning) => {
    const key = `${normalizedTitle(warning.title_de)}|${warning.target_date ?? ""}`;
    if (taskKeys.has(key) || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
