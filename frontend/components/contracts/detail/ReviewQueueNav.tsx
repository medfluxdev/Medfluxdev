"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { readReviewQueue } from "@/lib/review-queue";

const REVIEW_HREF = (id: string) => `/contracts/${id}?tab=documents&subtab=review`;

// Prüfreihenfolge aus der Liste „Zu prüfen“: Zurück / Weiter zum nächsten Vertrag (U5).
// Ohne gemerkte Reihenfolge (direkter Aufruf) wird nichts angezeigt.
export default function ReviewQueueNav({ contractId }: { contractId: string }) {
  const [queue, setQueue] = useState<string[]>([]);

  useEffect(() => {
    setQueue(readReviewQueue());
  }, [contractId]);

  const index = queue.indexOf(contractId);
  if (index < 0 || queue.length < 2) return null;
  const previous = index > 0 ? queue[index - 1] : null;
  const next = index < queue.length - 1 ? queue[index + 1] : null;
  return (
    <nav className="review-queue" aria-label="Prüfreihenfolge">
      <span>Vertrag {index + 1} von {queue.length} aus „Zu prüfen“</span>
      {previous ? <Link className="btn btn-sm" href={REVIEW_HREF(previous)}>Zurück</Link> : null}
      {next ? <Link className="btn btn-sm btn-primary" href={REVIEW_HREF(next)}>Weiter zum nächsten Vertrag</Link> : <Link className="btn btn-sm" href="/register?ansicht=review">Zurück zur Liste</Link>}
    </nav>
  );
}
