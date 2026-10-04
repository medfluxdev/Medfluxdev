# Database Configuration Guide for Medflux

## Three Database Configurations

### 1. Docker Compose (Recommended for Testing & Demo)
**When to use:** Integrated development, CI/CD, simple local testing
**Connection:** `postgresql+psycopg://medflux:medflux-local@postgres:5432/medflux`
**Setup:**
```bash
docker-compose up -d postgres
# DATABASE_URL is automatically set in docker-compose.yml
# No .env needed
```

### 2. Windows Local Development (Isolated Test Cluster)
**When to use:** Development on Windows with dedicated test PostgreSQL
**Port:** `127.0.0.1:55432`
**User:** `sr415_flow`
**Database:** `medflux_trial_20261001`

**Setup:**
```bash
# Set environment variable (one of):
set MEDFLUX_TEST_DATABASE_URL=postgresql+psycopg://sr415_flow:<PASSWORD>@127.0.0.1:55432/medflux_trial_20261001
# OR
set MEDFLUX_TRIAL_DSN=postgresql+psycopg://sr415_flow:<PASSWORD>@127.0.0.1:55432/medflux_trial_20261001

# Then run backend
cd backend
python -m uvicorn app.main:app --reload
```

**Note:** The backend validates DATABASE_URL through `app/testing/test_database.py` (fail-closed).
Must NOT set generic DATABASE_URL for this config – use the specific env vars above.

### 3. CI/CD (GitHub Actions)
**When to use:** Automated testing in cloud
**Connection:** Ephemeral PostgreSQL service in CI runner
**Setup:** Automatic, no configuration needed

---

## Configuration Decision Tree

```
Am I running tests locally?
├─ Yes, using Docker → Use config #1 (docker-compose)
├─ Yes, on Windows with WSL test cluster → Use config #2 (MEDFLUX_TEST_DATABASE_URL)
└─ Running in GitHub Actions → Use config #3 (CI provides DATABASE_URL)
```

## What NOT to Do

❌ Don't set generic `DATABASE_URL` for Windows dev (conflicts with fail-closed validation)
❌ Don't use .env as primary config (it's a template/example)
❌ Don't mix credentials between 5432 and 55432 (they use different users)

---

## Recommended .env Template

`backend/.env.example`:
```
# ============================================================
# Medflux Database Configuration
# ============================================================
# 
# For Docker Compose:
#   DATABASE_URL=postgresql+psycopg://medflux:medflux-local@postgres:5432/medflux
#
# For Windows Local Dev (WSL test cluster on port 55432):
#   MEDFLUX_TEST_DATABASE_URL=postgresql+psycopg://sr415_flow:<PASSWORD>@127.0.0.1:55432/medflux_trial_20261001
#   OR
#   MEDFLUX_TRIAL_DSN=postgresql+psycopg://sr415_flow:<PASSWORD>@127.0.0.1:55432/medflux_trial_20261001
#
# For CI/CD:
#   Automatic (no configuration needed)
#
# ============================================================

# Keep .env file empty in development
# Use environment variables for secrets
```

