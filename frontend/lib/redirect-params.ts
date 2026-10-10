type SearchParams = Record<string, string | string[] | undefined>;

/**
 * Ziel einer Weiterleitung mit allen gültigen Parametern der alten Adresse (U12).
 * `fixed` setzt Parameter des Ziels (z. B. ansicht=review) und hat Vorrang.
 * Der Fragmentteil (#…) bleibt beim Browser-Redirect ohnehin erhalten.
 */
export function withParams(target: string, searchParams: SearchParams | undefined, fixed: Record<string, string> = {}): string {
  const [path, existing] = target.split("?");
  const params = new URLSearchParams(existing ?? "");
  for (const [key, value] of Object.entries(searchParams ?? {})) {
    if (key in fixed || value === undefined) continue;
    for (const item of Array.isArray(value) ? value : [value]) params.append(key, item);
  }
  for (const [key, value] of Object.entries(fixed)) params.set(key, value);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}
