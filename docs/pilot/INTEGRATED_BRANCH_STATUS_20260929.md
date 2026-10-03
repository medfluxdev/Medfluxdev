# Integrated branch: local pilot preparation (NOT a released installer)

This branch is development work, not an approved distribution for Ahmed.
The existing release branch remains untouched. No GPU inference or database
migration has been performed as part of these GitHub source changes.

## Current source additions
- Active ContractWorkspace archive confirmation and navigation.
- Server-side deletion request, cancellation, confirmation and restoration
  with explicit opt-in, admin-role check, organization isolation and activity log.
- Typed client methods for deletion operations (deliberately not exposed as
  buttons until capability-based authorization and complete UI are ready).
- Source archive SHA256 manifest and offline integrity verifier.
- Static local pilot configuration preflight and gated setup entry point.

## Safe local pilot setup prerequisites
1. Use a NEW checkout and a NEW isolated PostgreSQL cluster. The cluster
   provisioning helper defaults to loopback port 55440 and refuses existing
   instance directories. It does not create the application database.
2. Create the MedFlux database in that NEW cluster with an explicit operator
   action; do not reuse or migrate existing user data.
3. Configure a private, untracked .env for loopback HTTP:
   APP_ENV=development, AUTH_ENABLED=true, MEDFLUX_INSECURE_DEV=false,
   AUTH_COOKIE_SECURE=false, BACKEND_HOST=127.0.0.1,
   unique APP_SECRET_KEY and a DATABASE_URL targeting the NEW isolated
   cluster on port 55440. Do not copy real passwords into logs or Git.
4. Run scripts/verify_local_pilot_preflight.ps1 as a read-only static check.
5. With explicit authorization for package installation and DB migrations,
   run scripts/setup_isolated_pilot.ps1. This calls the preflight first.
   The existing setup may require interactive local-admin password entry.
6. Perform a separate runtime, login, API, frontend and AI integration
   acceptance test. Passing preflight does not establish readiness.

IMPORTANT: APP_ENV=development is only for loopback HTTP. A remotely
accessible pilot must use HTTPS, APP_ENV=pilot, secure cookies and a
separate provisioning flow. Do not weaken runtime checks.

## Open implementation and acceptance gates
- Capability-driven deletion UI and final policy decision.
- Confirm endpoint signatures and audit semantics in the full test suite.
- Verify the pilot bootstrap, DB creation and secure runtime end-to-end.
- Update the legacy installation guide after installer acceptance.
- Run the final green static suite and authorized yellow isolated DB suite.
- GPU/Ollama testing requires separate red authorization.
- Do not merge, ship, or modify Ahmed's running installation without approval.
