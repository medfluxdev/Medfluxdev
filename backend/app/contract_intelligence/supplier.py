"""Supplier performance rollup from explicit findings and obligations."""

from __future__ import annotations

from collections import Counter


def summarize_supplier_performance(rows: list[dict]) -> dict:
    counts = Counter()
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] += 1
    total = sum(counts.values())
    breached = counts.get("breached", 0)
    return {
        "total_obligations": total,
        "breached_obligations": breached,
        "breach_rate": (breached / total) if total else None,
        "status_counts": dict(counts),
    }
