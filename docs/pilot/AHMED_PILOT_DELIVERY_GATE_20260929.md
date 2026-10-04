# Ahmed Pilot — narrow delivery gate (no merge or deployment)

Purpose: deliver ONE existing MedFlux pilot build to Ahmed for real-contract feedback. This is a delivery gate, not a new architecture phase. DRIFT-1 2D reported PASS (11/11 opt-in); seven historical databases remain unavailable/unverified and are not a prerequisite for a clean separate pilot database.

## Required evidence before handoff
1. Confirm exact source branch/commit and existing feature coverage; no unreviewed merge into JAMAL. List unresolved blocking issues only.
2. Clean separate pilot configuration and new isolated pilot DB, NOT PG55432 disposable migration test DB and NOT an existing production DB. Never copy real patient or contract data into a test fixture. Provisioning a pilot DB requires Jamal's explicit approval after reporting exact location and operations.
3. Actual user journey: login and org isolation; import PDF/DOCX; document persistence; AI analysis with a vision-capable configured model; deterministic extraction/evidence navigation; contract list/detail; post-save human review; permissions and error handling. Report each as verified, blocked, or not implemented; never claim manual no-AI flow exists if it does not.
4. Use synthetic/nonconfidential contract for first UI walkthrough. Run a minimal targeted test suite and a browser walkthrough; no GPU/Ollama until Jamal explicitly approves the RED resource stage. No uncontrolled 57-call Frankfurt benchmark.
5. Prepare a reproducible startup script/instructions, exact pinned revision, environment template without secrets, safe access method, known limitations and a 5-case feedback form for Ahmed. Do not expose Jamal's local machine, ports or credentials to the internet. No distribution of internal source, binaries or actual contracts without Jamal's explicit delivery approval.

## Stop conditions
If any core flow is missing or unsafe, report the narrow blocker and minimal assistant-owned fix; do not launch a new broad test campaign. OpenCode only tests and reports. Assistant owns GitHub code. No merge/deploy without Jamal approval.
