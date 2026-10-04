# Ahmad review — safe local launch and explicit limits

Status: **prepared, not runtime-verified on Jamal's Windows machine**, because the connected self-hosted runner currently has **no Docker CLI**. Do not call this a deployed or fully accepted build until G06 end-to-end checks pass.

## Delivery source

Review code: branch `review/ahmad-hospital-20260926`, which does not merge or modify `JAMAL`, Ahmad's branch, or the existing local Visual-First experiment. Features added for Ahmad: explicit import settings confirmation (AI + human review workflow only), scoped cost-center number lookup, stakeholder keep/change/remove/defer form. Existing backend remains authoritative. No original hospital PDF, approved budgets or sensitive information is bundled.

## Preferred separate preview when Docker is available (Windows PowerShell)

1. Obtain a clean checkout of the named review branch **in a new folder**, not inside `Medflux-Integrated-Test` or `Medflux-VisualFirst-Experiment`. Verify an empty folder and branch before running anything.
2. Install/start Docker Desktop, confirm `docker version` and `docker compose version` succeed.
3. From the isolated checkout root, run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\prepare_ahmad_review.ps1`. This generates unique secrets only in local ignored `.env.ahmad.local`.
4. Inspect `docker compose --env-file .env.ahmad.local -f docker-compose.ahmad-review.yml config`. Confirm the only frontend/backend host binds are 127.0.0.1:13000 and 127.0.0.1:18000; the Postgres container has **no host bind** and uses isolated Docker named volumes. If port conflict exists, stop and explicitly replan ports and frontend build-time API URL; never point to existing ports 3000/8000 or existing MedFlux data.
5. After independent acceptance of this Compose configuration, run `docker compose --env-file .env.ahmad.local -f docker-compose.ahmad-review.yml up --build -d`; inspect backend health at `http://localhost:18000/ready` and frontend at `http://localhost:13000`. Do **not** use real patient or financial information.
6. Create a review-only developer account interactively after first backend DB migration: `docker compose --env-file .env.ahmad.local -f docker-compose.ahmad-review.yml exec backend python -m app.create_developer --email example@review.invalid --name "Pilot Developer"`. Password is prompted and must not be written to GitHub/logs. Set up a dedicated sample organization/hospital/department in the application before testing scoped pages; avoid giving Ahmad unrestricted developer credentials if he is remote. Use a least-privilege scoped review account when account workflows have been UAT-verified.
7. User-facing pages: `/import` (current-scope confirmation; only AI + human review available), `/kostenstellen-suche` (real scoped master lookup; budget unavailable without approved finance imports), `/analysen` (existing live scoped portfolio), `/ahmad-review` (feedback copy, **not autosaved**). Copy Ahmad's notes before closing the review page.

## Important limits and security
- This Compose stack is a **localhost-only developmental evaluation** with an isolated PostgreSQL 18 database and separate protected document volume. It is **not** approval for hospital deployment or remote exposure. Do not share port forward/public tunnel.
- The existing backend image's Linux OCR/vision dependency readiness, Docker image build, first-start migrations, AI provider connectivity from Docker, login/scopes and actual PDF end-to-end **remain untested**. A complete runtime test is mandatory before sending this procedure as a guaranteed one-click installer.
- No automatic backups of the pilot volumes are yet provided; destroy only isolated pilot resources after explicit confirmation, never with blanket `docker volume prune`.
- Visual-First local experimental code may contain newer uncommitted work absent from this GitHub review branch. Do not overwrite/copy it without a reviewed import, version comparison and new test run.
- An installed Windows runner does not imply Docker availability. The 2026-09-26 audit [run 36244336198](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36244336198) reported `DOCKER_CLI_AVAILABLE=False`.
