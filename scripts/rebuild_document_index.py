#!/usr/bin/env python3
"""Rebuild document index from actual file storage.

Scans backend/data/contracts/ for all document folders and generates
a manifest with SHA-256 hashes for each document's original.pdf.

Usage:
    python scripts/rebuild_document_index.py --contracts-dir backend/data/contracts
    
    Or from repository root:
    python scripts/rebuild_document_index.py
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def rebuild_index(contracts_dir: Path) -> Dict[str, Any]:
    """Rebuild index from actual files in contracts directory.
    
    Args:
        contracts_dir: Path to the contracts directory
        
    Returns:
        Dictionary with structure: {
            "version": "1.0",
            "timestamp": "2026-10-03T...",
            "documents": {
                "document_id": {
                    "storage_key": "relative/path/to/document",
                    "original_filename": "contract.pdf",
                    "file_size_bytes": 352267,
                    "sha256": "...",
                    "import_status": "imported"
                }
            },
            "summary": {
                "total_documents": 35,
                "total_size_bytes": ...
            }
        }
    """
    contracts_dir = Path(contracts_dir)
    if not contracts_dir.exists():
        raise FileNotFoundError(f"Contracts directory not found: {contracts_dir}")
    
    documents = {}
    total_size = 0
    count = 0
    
    print(f"Scanning {contracts_dir} for documents...")
    
    # Scan all subdirectories (each is a document)
    for doc_folder in sorted(contracts_dir.iterdir()):
        if not doc_folder.is_dir() or doc_folder.name.startswith('.'):
            continue
        
        # Look for original.pdf (primary format)
        original_file = doc_folder / "original.pdf"
        if not original_file.exists():
            print(f"  ⚠️  No original.pdf in {doc_folder.name} (skipped)")
            continue
        
        # Compute SHA-256 hash
        sha256 = compute_sha256(original_file)
        file_size = original_file.stat().st_size
        
        # Build storage key (relative path)
        storage_key = f"{doc_folder.name}/original.pdf"
        
        documents[doc_folder.name] = {
            "storage_key": storage_key,
            "original_filename": "original.pdf",
            "file_size_bytes": file_size,
            "sha256": sha256,
            "import_status": "imported"
        }
        
        total_size += file_size
        count += 1
        
        if count % 5 == 0:
            print(f"  ✓ Processed {count} documents...")
    
    print(f"\n✅ Index rebuild complete: {count} documents, {total_size:,} bytes total")
    
    return {
        "version": "1.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "documents": documents,
        "summary": {
            "total_documents": count,
            "total_size_bytes": total_size
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild document index from file storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/rebuild_document_index.py
  python scripts/rebuild_document_index.py --contracts-dir backend/data/contracts
  python scripts/rebuild_document_index.py --output /tmp/index.json
        """
    )
    parser.add_argument(
        "--contracts-dir",
        type=Path,
        default=Path("backend/data/contracts"),
        help="Path to contracts directory (default: backend/data/contracts)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: contracts_dir/.index.json)"
    )
    
    args = parser.parse_args()
    
    try:
        index = rebuild_index(args.contracts_dir)
        
        # Determine output path
        output_path = args.output or (args.contracts_dir / ".index.json")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write manifest
        with open(output_path, "w") as f:
            json.dump(index, f, indent=2)
        
        print(f"\n📝 Index written to: {output_path}")
        print(f"   Size: {output_path.stat().st_size:,} bytes")
        print(f"\nVerify with:")
        print(f"  python -c \"import json; d=json.load(open('{output_path}')); print(f'Documents: {{len(d[\\\"documents\\\"])}}')\"")
        
        return 0
    
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
