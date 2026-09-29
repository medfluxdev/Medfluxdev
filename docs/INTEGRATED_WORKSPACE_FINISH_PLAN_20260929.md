# MedFlux integrated workspace — finish criteria

Development branch: feature/integrated-release-build-20260929.
Do not merge protected JAMAL, alter Ahmed's independent installation, or run expensive workloads without owner approval.

## Product experience
1. Retain existing design and eight responsive screens. Preserve route, selected contract, folder, scroll position and work context while the Qwen assistant opens, collapses or resizes.
2. Floating Qwen must be connected to the actual backend with authenticated organization and hospital/department scope; only the administrator chooses a supported vision model. No mock success, no unauthorized cross-contract citations. Show loading, errors, cancellation and exact evidence links.
3. Contract 360: import, extraction, review, source PDF, calculations, lifecycle, billing, archive and permissions all use live typed backend APIs.
4. Navigation: dashboard, contracts, review, work queue, equipment, analytics, archive, audit, admin and settings remain coherent; responsive keyboard-accessible focus and dialogs.
5. Deletion is separate from archival: server opt-in, admin-only, request/confirm/cancel/restore, audit, no hard deletion. The administrative queue must paginate.

## Final integration acceptance — one OpenCode run after source completion
- Fetch and fast-forward the approved feature branch in the existing local checkout; do not touch Ahmed's independent machine, branch or release package.
- Install dependencies only after permission; confirm environment and isolated DB before migration.
- Frontend typecheck/lint/build and backend test suite; targeted lifecycle, archive, deletion, authorization, organization/scope, document evidence and assistant API checks.
- End-to-end walkthrough of the real UI on desktop/tablet/mobile; test actual backend and Ollama only with explicit GPU approval.
- Confirm navigation and Qwen panel preserve work context; no claims of actual integration until verified.
- Deliver a single consolidated report with pass/fail evidence, reproduction and remaining blockers. No automatic protected-branch merge or deployment.

## Current status
Deletion administration and archive wiring have source commits but have not been locally tested. UI screenshots and interaction-only mocks are not evidence of real backend/Ollama integration.
