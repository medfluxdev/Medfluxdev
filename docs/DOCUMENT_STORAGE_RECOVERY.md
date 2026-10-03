# Document Storage Recovery Procedure

## Current State

### Issue: Document Storage Split & Index Drift

**Locations:**
- Root-level `data/contracts/` - **EMPTY** (.gitkeep only)
- Backend `backend/data/contracts/` - **35 document folders** with PDFs
- Manifest `.index.json` - **EMPTY** ({})
- Database `document_file` table - **3 records** (doesn't match 35 documents)

### Root Cause

The `contracts_dir` setting in `backend/app/core/config.py` uses a relative path:
```python
contracts_dir: str = "./data/contracts"
```

When the backend starts from different working directories:
- From `backend/` directory: `./data/contracts` → `backend/data/contracts/` ✓
- From root `Medflux/` directory: `./data/contracts` → `data/contracts/` ✗

This led to documents being stored in two different locations without proper manifest tracking.

### Consequences

1. **Duplicate Detection Broken**: SHA-256 index is empty, so duplicates aren't detected
2. **Data Loss Risk**: Documents exist on disk but aren't indexed in the manifest
3. **Database Drift**: `document_file` table doesn't match actual documents
4. **Import Fragility**: Future imports might go to the wrong location

---

## Recovery Steps

### Step 1: Verify Current State

```bash
# Count documents on disk (should be 35)
find backend/data/contracts -maxdepth 1 -type d | wc -l

# Check manifest (should be empty {})
cat backend/data/contracts/.index.json

# Check database (should be 3)
psql -U sr415_flow -d medflux_trial_20261001 -c "SELECT COUNT(*) FROM document_file;"
```

### Step 2: Generate SHA-256 Hashes

Create a recovery script to scan existing documents and compute their SHA-256:

```python
import hashlib
import json
from pathlib import Path

contracts_dir = Path("backend/data/contracts")
index = {}

for doc_folder in contracts_dir.iterdir():
    if not doc_folder.is_dir():
        continue
    
    # Find original file (.pdf or .docx)
    original = None
    for ext in [".pdf", ".docx"]:
        candidate = doc_folder / f"original{ext}"
        if candidate.is_file():
            original = candidate
            break
    
    if not original:
        print(f"⚠️  Skip {doc_folder.name}: no original file found")
        continue
    
    # Compute SHA-256
    sha256 = hashlib.sha256()
    with open(original, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    
    # Record in manifest
    document_id = doc_folder.name
    index[sha256.hexdigest()] = {
        "document_id": document_id,
        "original_filename": original.name,
        "size_bytes": original.stat().st_size,
        "created_at": original.stat().st_birthtime,  # or mtime on Linux
    }
    
    print(f"✓ Indexed {document_id}: {original.name}")

# Save manifest
with open(contracts_dir / ".index.json", "w") as f:
    json.dump(index, f, indent=2)

print(f"\n✅ Manifest rebuilt: {len(index)} documents indexed")
```

### Step 3: Reconcile Database Records

Query the database to find which documents are actually imported and update `document_file` rows:

```sql
-- Check current state
SELECT id, document_id, original_filename, created_at FROM document_file LIMIT 5;

-- Identify missing document_file records
-- (For now, documents exist on disk but aren't in the DB)
```

If documents are missing from the database, they can be re-imported using the Web UI or an import script.

### Step 4: Update Configuration for Consistency

**Add explicit absolute path to backend/.env:**

```bash
# For development, make contracts_dir absolute to avoid cwd issues
CONTRACTS_DIR=/path/to/Medflux/backend/data/contracts
```

**Update AGENTS.md** with explicit instruction:
> Always start the backend from the `backend/` directory to ensure relative paths resolve correctly.
> Or set `CONTRACTS_DIR` to an absolute path.

### Step 5: Document the Canonical Location

Update `AGENTS.md` section to state:
```
Document Storage Location (CANONICAL):
  backend/data/contracts/

  - Do NOT split documents between data/contracts/ and backend/data/contracts/
  - All imports write to backend/data/contracts/
  - Manifest (.index.json) is maintained in backend/data/contracts/
  - Always start backend from backend/ directory to ensure relative paths resolve correctly
```

---

## Testing the Fix

### Manual Test

1. Import a new PDF contract using the Web UI
2. Check that it appears in `backend/data/contracts/<id>/original.pdf`
3. Verify the manifest was updated: `cat backend/data/contracts/.index.json`
4. Verify the database was updated: `SELECT COUNT(*) FROM document_file;`

### Automated Test

Add a test to verify:
- Document can be imported
- Manifest is updated
- Database record is created
- Duplicate detection works (import the same file again)

---

## Long-term Solutions

### 1. Make contracts_dir Absolute in Production

In `backend/app/core/config.py`:
```python
from pathlib import Path

contracts_dir: str = str(Path(__file__).parent.parent.parent.parent / "backend" / "data" / "contracts")
```

### 2. Add Validation on Startup

Backend should validate on startup:
```python
# On backend start:
if not Path(contracts_dir).is_dir():
    raise RuntimeError(f"Document storage not found: {contracts_dir}")

index = load_manifest(contracts_dir)
actual_dirs = count_document_folders(contracts_dir)
if len(index) < actual_dirs * 0.8:  # Less than 80% indexed
    logger.warning(f"Document index drift detected: {len(index)} indexed, {actual_dirs} on disk")
```

### 3. Periodic Reconciliation

Add a background task to periodically:
- Verify all documents on disk are in the manifest
- Verify all manifest entries exist on disk
- Detect orphaned database records

---

## Migration Checklist

- [ ] Count documents on disk (backend/data/contracts/)
- [ ] Verify manifest is empty (.index.json = {})
- [ ] Compute SHA-256 hashes for all documents
- [ ] Rebuild .index.json manifest
- [ ] Check database consistency (document_file table)
- [ ] Test import of new document
- [ ] Verify duplicate detection works
- [ ] Update documentation in AGENTS.md
- [ ] Set CONTRACTS_DIR to absolute path (if needed)
- [ ] Add startup validation

---

## Reference

- **Storage Code**: `backend/app/documents/storage.py`
- **Import Code**: `backend/app/documents/service.py`
- **Configuration**: `backend/app/core/config.py`
- **Manifest Format**: `.index.json` in document storage directory

