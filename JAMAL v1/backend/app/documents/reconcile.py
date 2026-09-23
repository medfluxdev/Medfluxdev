"""Local admin command for controlled document resume/reconciliation.

Examples (run from ``backend``):

    python -m app.documents.reconcile --organization-slug krankenhaus \
        --resume-version <uuid>

    python -m app.documents.reconcile --organization-slug krankenhaus \
        --legacy-document-id <legacy-hex-id>

    python -m app.documents.reconcile --organization-slug krankenhaus \
        --all-legacy --limit 25 --dry-run

No public bulk endpoint is exposed before STEP 16 authorization.  Actual work is
delegated to ``DocumentProcessingService``; this module contains no processing
pipeline of its own.
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from app.documents.processing import DocumentProcessingService
from app.documents.storage import DocumentStorage, StorageError
from app.core.config import settings


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Resume DB documents or reconcile selected legacy originals."
    )
    parser.add_argument("--organization-slug", required=True)
    parser.add_argument("--resume-version", action="append", default=[])
    legacy = parser.add_mutually_exclusive_group()
    legacy.add_argument("--legacy-document-id", action="append", default=[])
    legacy.add_argument("--all-legacy", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--as-of-date", type=date.fromisoformat)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.resume_version and not args.legacy_document_id and not args.all_legacy:
        parser.error(
            "select --resume-version, --legacy-document-id, or explicit --all-legacy"
        )
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    return args


def _safe_result(result) -> dict:
    return {
        "document_id": result.document_id or None,
        "document_version_id": result.document_version_id or None,
        "original_filename": result.original_filename,
        "status": result.status,
        "analysis_status": result.analysis_status,
        "contract_id": result.contract_id,
        "requires_review": result.requires_review,
        "message": result.message,
    }


def main(argv=None) -> int:
    args = _parse_args(argv)
    storage = DocumentStorage(settings.contracts_dir)
    service = DocumentProcessingService(storage=storage)

    if args.dry_run:
        legacy_records = []
        if args.legacy_document_id or args.all_legacy:
            try:
                legacy_records = storage.legacy_records(
                    document_ids=(
                        args.legacy_document_id
                        if args.legacy_document_id
                        else None
                    ),
                    limit=args.limit,
                )
            except StorageError as exc:
                print(json.dumps({"status": "failed", "message": str(exc)}))
                return 1
        payload = {
            "dry_run": True,
            "resume_versions": args.resume_version,
            "legacy_documents": [
                {
                    "document_id": record.get("document_id"),
                    "original_filename": record.get("original_filename"),
                    "sha256": record.get("sha256"),
                }
                for record in legacy_records
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    results = []
    for version_id in args.resume_version:
        results.append(
            service.resume_document(
                organization_slug=args.organization_slug,
                document_version_id=version_id,
                as_of_date=args.as_of_date,
            )
        )
    if args.legacy_document_id or args.all_legacy:
        results.extend(
            service.reconcile_legacy(
                organization_slug=args.organization_slug,
                document_ids=(
                    args.legacy_document_id
                    if args.legacy_document_id
                    else None
                ),
                limit=args.limit,
                as_of_date=args.as_of_date,
            )
        )

    safe_results = [_safe_result(result) for result in results]
    print(json.dumps(safe_results, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] in {"failed", "rejected"} for item in safe_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
