# Ahmed local analysis package — release checklist

Goal: Ahmed installs MedFlux on HIS OWN computer, imports HIS contract, runs local vision analysis with RTX 4070 12GB, and views the saved result and PDF page evidence. This is not a remote connection to Jamal's computer.

## Current status
This release branch contains a SOURCE-ONLY packaging helper, not a tested downloadable installer. The helper archives tracked code at the exact reviewed HEAD and fails on dirty tree or suspicious tracked secret/data paths. GitHub access for Ahmed is NOT required if Jamal sends the resulting ZIP privately after validation and authorization. No release is approved until actual fresh-machine installation and full UI analysis succeed.

## Implementation checklist (assistant-owned before release)
- Deliver a Windows-first local installation path with explicit dependency checks, reversible fresh PostgreSQL provisioning on Ahmed's machine, isolated app storage, safe admin bootstrap, secure localhost session behavior, and controlled Ollama/model selection. Never reuse 55432/5432/5444 assumptions from Jamal's machine.
- Review and fix bootstrap: existing scripts/setup.ps1 uses ensure_local_admin restricted to development/test; APP_ENV=pilot also requires AUTH_COOKIE_SECURE=true and HTTPS. Do not falsely promise current setup.ps1 works in pilot mode. Create a proper approved local installation procedure and test it.
- Ensure source archive excludes .env, credentials, real contracts, test databases, logs, model weights, and other sensitive artifacts. Verify on a clean checkout and inspect archive manifest.
- Target one organization only: global model selection is NOT tenant-scoped. Manual no-AI import NOT implemented. No production readiness claims.
- Target smoke: fresh isolated installation -> admin login -> synthetic PDF import -> model selection -> bounded real Ollama vision run -> saved contract results -> click PDF evidence -> human post-save review -> restart -> results persist. Capture exact GPU peak and call count. No large Frankfurt benchmark.
- After success, give Ahmed installation instructions in Arabic, required prerequisites, exact ZIP checksum, private handoff method, expected limitations, and feedback form. If Ahmed uses Linux rather than Windows, create and test a separate Linux path.

## Permissions and resources
Green: inspect code, write docs, package source. Yellow: installing dependencies and fresh DB creation on an approved machine, requires Jamal's approval of exact operations. Red: GPU/Ollama/model runtime, requires Jamal's explicit approval before using Jamal's GPU. Ahmed's own GPU runs require Ahmed's permission. Never merge into JAMAL, deploy, open network ports, or touch production without explicit approval.

## Verification boundary
Existing DRIFT-1 synthetic migration checks and prior unit suites are supporting evidence, not proof of a working Ahmed installer or runtime vision analysis. Keep seven historical DB digests UNVERIFIED.
