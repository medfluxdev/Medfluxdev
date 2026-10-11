"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { getPermissionMatrix, type PermissionMatrix } from "@/lib/domain-api/access";

export type PermissionKey =
  | "partner.edit"
  | "device_type.edit"
  | "catalog.admin"
  | "organization.admin"
  | "review.settings"
  | "audit.view"
  | "export"
  | "contract.create"
  | "contract.view_deleted";

const cache = new Map<string, Promise<PermissionMatrix>>();

// Nur fuer Tests: zwischengespeicherte Rechte-Matrizen verwerfen.
export function resetPermissionCache() {
  cache.clear();
}

/**
 * Darstellungsrechte aus der Rechte-Matrix des Backends (`/api/permissions`).
 * Beruecksichtigt die "Ansicht als Rolle". Solange die Matrix nicht geladen ist,
 * gilt nichts als erlaubt (nur Lesen). Das Backend prueft jede Aenderung selbst.
 */
export function usePermissions() {
  const { organizationSlug, role, account, previewOf } = useAuth();
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(null);

  useEffect(() => {
    if (!organizationSlug) return;
    let active = true;
    let pending = cache.get(organizationSlug);
    if (!pending) {
      pending = getPermissionMatrix(organizationSlug);
      cache.set(organizationSlug, pending);
      pending.catch(() => cache.delete(organizationSlug));
    }
    pending.then((value) => { if (active) setMatrix(value); }).catch(() => { if (active) setMatrix(null); });
    return () => { active = false; };
  }, [organizationSlug]);

  const loaded = matrix !== null;
  function can(permission: PermissionKey): boolean {
    if (account?.is_developer && !previewOf) return true;
    if (!matrix || !role) return false;
    return matrix.permissions.find((item) => item.key === permission)?.roles.includes(role) ?? false;
  }
  return { can, loaded };
}
