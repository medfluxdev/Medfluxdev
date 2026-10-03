"""Authority and precedence helpers.

No contractual meaning is invented here. Qwen/human review supplies relations
and authority. This module only validates and orders explicit authority facts.
"""

from __future__ import annotations

from collections import defaultdict

from app.contract_intelligence.models import ContractRelation


def validate_authority(relations: list[ContractRelation]) -> list[str]:
    issues: list[str] = []
    seen: dict[tuple, set[str]] = defaultdict(set)
    for relation in relations:
        key = (
            relation.source_document_version_id,
            relation.target_document_version_id,
            relation.relation_type,
        )
        seen[key].add(relation.authority)
        if relation.authority != "unknown" and not relation.evidence:
            issues.append(f"{relation.relation_type}: authority without evidence")
    for key, values in seen.items():
        concrete = values - {"unknown"}
        if len(concrete) > 1:
            issues.append(f"authority conflict for {key}")
    return issues


def authority_rank(authority: str) -> int:
    return {"primary": 0, "secondary": 1, "unknown": 2}.get(authority, 2)
