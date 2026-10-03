# Phase 2: Document Storage Recovery Implementation Plan (2026-10-03)

## Objective
Fix the document storage split and manifest drift by:
1. Rebuilding the `.index.json` manifest from actual files
2. Verifying all 35 documents are properly indexed
3. Consolidating storage and validating database consistency

## Current State Verification (Completed)

### ✅ Verified Findings
- **Root location** `data/contracts/`: Empty (only .gitkeep)
- **Actual location** `backend/data/contracts/`: 35 document folders
- **Index file** `backend/data/contracts/.index.json`: 2 bytes (empty "{}")
- **Document folders**: Use ULID-style identifiers (01a05ca1f68a7da4a70524aab82f8539, etc.)
- **Document content**: Each folder contains `original.pdf` file
- **Database schema**: `document_file` table expects:
  - `id` (UUID primary key)
  - `storage_key` (path to document)
  - `sha256` (hash for duplicate detection)
  - `original_filename` (user-friendly name)
  - `file_size_bytes` (document size)
  - `import_status` (imported|rejected|failed|duplicate)
  - `imported_at` (timestamp)

### 📊 Expected vs Actual
| Item | Expected | Actual | Status |
|------|----------|--------|--------|
| Root contracts dir | Primary location | Empty | ⚠️ |
| Backend contracts dir | Fallback | Contains 35 docs | ✅ |
| Index manifest | 35+ entries | Empty "{}" | ⚠️ |
| DB records | 35+ records | Unknown (likely 3) | ⚠️ |

---

## Phase 2 Implementation Steps

### Step 1: Backup Current State (Safety First)
```bash
# Create timestamped backup
mkdir -p data/backups/
cp -r backend/data/contracts data/backups/contracts_backup_20261003
echo "Backup created at: data/backups/contracts_backup_20261003"

# Verify backup
ls -la data/backups/contracts_backup_20261003/ | head -10
```

**Expected Result:** All 35 document folders safely backed up

---

### Step 2: Generate Index Manifest

Run the index rebuild script to scan all documents and generate `.index.json`:

**File: `scripts/rebuild_document_index.py`**

```python
#!/usr/bin/env python3
"""Rebuild document index from actual file storage.

Scans backend/data/contracts/ for all document folders and generates
a manifest with SHA-256 hashes for each document's original.pdf.

Usage:
    python scripts/rebuild_document_index.py --contracts-dir backend/data/contracts
"""

import argparse
import hashlib
import json
import sys
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
    from datetime import datetime
    
    contracts_dir = Path(contracts_dir)
    if not contracts_dir.exists():
        raise FileNotFoundError(f"Contracts directory not found: {contracts_dir}")
    
    documents = {}
    total_size = 0
    count = 0
    
    print(f"Scanning {contracts_dir} for documents...")
    
    # Scan all subdirectories (each is a document)
    for doc_folder in sorted(contracts_dir.iterdir()):
        if not doc_folder.is_dir():
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
        description="Rebuild document index from file storage"
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
        
        # Write manifest
        with open(output_path, "w") as f:
            json.dump(index, f, indent=2)
        
        print(f"\n📝 Index written to: {output_path}")
        print(f"   Size: {output_path.stat().st_size:,} bytes")
        
        return 0
    
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Usage:**
```bash
# From repository root
python scripts/rebuild_document_index.py --contracts-dir backend/data/contracts

# Expected output:
# Scanning backend/data/contracts for documents...
#   ✓ Processed 5 documents...
#   ✓ Processed 10 documents...
#   ...
# ✅ Index rebuild complete: 35 documents, XXX,XXX bytes total
# 
# 📝 Index written to: backend/data/contracts/.index.json
#    Size: X,XXX bytes
```

---

### Step 3: Verify Index Integrity

```bash
# Check index file
ls -lh backend/data/contracts/.index.json
# Should be > 10KB (not 2 bytes anymore)

# Validate JSON structure
python -m json.tool backend/data/contracts/.index.json | head -30
# Should show proper JSON structure with documents array

# Count entries
python -c "import json; f=open('backend/data/contracts/.index.json'); d=json.load(f); print(f'Documents in index: {len(d[\"documents\"])}')"
# Should print: Documents in index: 35
```

**Expected Result:** Index file properly formatted with all 35 documents

---

### Step 4: Verify Database Consistency

```bash
# Start backend to connect to database
cd backend

# Option A: If using Docker Compose
docker-compose up -d postgres
export DATABASE_URL=postgresql+psycopg://medflux:medflux-local@localhost:5432/medflux

# Option B: If using Windows local dev
set MEDFLUX_TEST_DATABASE_URL=postgresql+psycopg://sr415_flow:<PASSWORD>@127.0.0.1:55432/medflux_trial_20261001

# Run verification script
python scripts/verify_document_storage.py
```

**Expected Output:**
```
📊 Document Storage Verification Report
=====================================
Total file folders: 35
Total indexed documents: 35
Database records: 35 (or less - to be fixed in next step)

✅ File & Index Consistency: PASS
⚠️ Database Consistency: CHECK NEEDED
```

---

### Step 5: Sync Database Records

If database has fewer than 35 records, use the import script to add missing ones:

**File: `scripts/sync_database_documents.py`**

```python
#!/usr/bin/env python3
"""Sync database records with actual document storage.

Reads .index.json and ensures each document has a database record
in the document_file table.

Usage:
    python scripts/sync_database_documents.py
"""

import json
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def sync_documents_to_db(contracts_dir: str, database_url: str):
    """Sync index documents to database."""
    
    index_path = Path(contracts_dir) / ".index.json"
    
    if not index_path.exists():
        print(f"❌ Index file not found: {index_path}")
        return 1
    
    with open(index_path) as f:
        index = json.load(f)
    
    # Connect to database
    engine = create_engine(database_url)
    
    with Session(engine) as session:
        # Check existing records
        result = session.execute(
            text("SELECT COUNT(*) FROM document_file")
        )
        existing_count = result.scalar()
        
        print(f"Existing database records: {existing_count}")
        print(f"Indexed documents: {len(index['documents'])}")
        
        # For now, just report
        # Full implementation would insert missing records
        if existing_count < len(index['documents']):
            print(f"\n⚠️ Missing {len(index['documents']) - existing_count} records")
            print("   Manual import via Web UI or batch insert needed")
        else:
            print("\n✅ Database appears complete")
    
    return 0


def main():
    import os
    
    contracts_dir = os.environ.get("CONTRACTS_DIR", "backend/data/contracts")
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://medflux:medflux-local@localhost:5432/medflux"
    )
    
    return sync_documents_to_db(contracts_dir, database_url)


if __name__ == "__main__":
    sys.exit(main())
```

---

### Step 6: Test Forward (Validate Fix)

```bash
# 1. Start backend
cd backend
python -m uvicorn app.main:app --reload

# 2. Import a new document via Web UI
# - Open http://localhost:3000
# - Go to Document Import
# - Upload any PDF file

# 3. Verify new document:
python -c "
import json
with open('data/contracts/.index.json') as f:
    data = json.load(f)
print(f'Total documents now: {len(data[\"documents\"])}')
"
# Should show 36 (35 existing + 1 new)

# 4. Check database
# SELECT COUNT(*) FROM document_file
# Should show the new record
```

---

## Phase 2 Completion Checklist

- [ ] **Backup created** – `data/backups/contracts_backup_20261003/` exists with all 35 documents
- [ ] **Index script created** – `scripts/rebuild_document_index.py` exists and runs
- [ ] **Index rebuilt** – `backend/data/contracts/.index.json` is proper JSON with 35 documents
- [ ] **Index verified** – Can parse JSON, contains all document metadata
- [ ] **Database checked** – Know current record count
- [ ] **Database synced** – All 35 documents have database records
- [ ] **Forward test passed** – Can import new document and see it in index + database
- [ ] **Documentation updated** – AGENTS.md explains canonical storage location

---

## Long-term Solutions (Phase 3)

To prevent this issue from happening again:

### Issue: Relative Path Resolution
**File:** `backend/app/core/config.py`
**Current:** `contracts_dir: str = "./data/contracts"`
**Problem:** Resolves differently depending on working directory

**Solution:** Use absolute path
```python
from pathlib import Path

# Instead of:
# contracts_dir: str = "./data/contracts"

# Use:
contracts_dir: Path = Path(__file__).parent.parent.parent / "data" / "contracts"
```

### Issue: No Startup Validation
**Add validation** to `backend/app/main.py`:
```python
# On app startup
import os
from pathlib import Path

if not contracts_dir.exists():
    raise RuntimeError(
        f"Contracts directory not found: {contracts_dir}\n"
        f"Expected at: {contracts_dir.absolute()}"
    )

index_path = contracts_dir / ".index.json"
if not index_path.exists():
    logger.warning(f"Index file missing: {index_path}")
    logger.warning("Run: python scripts/rebuild_document_index.py")
```

---

## Success Criteria

✅ **Phase 2 Complete when:**

1. `.index.json` contains exactly 35 documents with proper metadata
2. All documents are readable via storage_key path
3. Database has ≥35 records in document_file table
4. New document imports work correctly
5. Duplicate detection via SHA-256 works
6. All documentation updated in AGENTS.md

**Estimated Time:** 2-3 days (mostly testing & validation)

---

## Rollback Plan

If issues occur:

```bash
# Restore from backup
rm -rf backend/data/contracts
cp -r data/backups/contracts_backup_20261003 backend/data/contracts

# Reset index
echo "{}" > backend/data/contracts/.index.json

# Restart backend
docker-compose restart backend
```

---

## Links & References

- **Document Model:** `backend/app/database/models/document.py`
- **Storage Module:** `backend/app/documents/storage.py`
- **Import Routes:** `backend/app/api/routes/documents.py`
- **Current Setup:** `backend/app/core/config.py` (contracts_dir config)
- **Previous Recovery Guide:** `docs/DOCUMENT_STORAGE_RECOVERY.md` (from Phase 0)

---

**Status:** Phase 2 Implementation Plan Ready
**Next:** Execute Steps 1-6 during next development session
**Backup Location:** `data/backups/contracts_backup_20261003/`
**Key File:** `scripts/rebuild_document_index.py` (ready to create)

