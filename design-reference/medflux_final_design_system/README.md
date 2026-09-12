# Medflux — Final Design System (Fixture-Free Reference)

Status: approved implementation reference.

## Critical rule: NO VISUAL FIXTURES

This package intentionally contains **no fake contracts, suppliers, devices, amounts,
audit events, search results, notification items, timestamps, quality counters or example records**.

Every customer-facing data region must do exactly one of the following:
1. Render real data from the Medflux backend/API.
2. Render a truthful Empty / Loading / Error / Unavailable state.

Do not add hard-coded sample business data to production pages.

## Included pages
- `index.html` — Übersicht
- `contract360.html` — Contract 360
- `evidence-viewer.html` — Nachweisansicht
- `archiv.html` — Archiv
- `einstellungen.html` — Einstellungen
- `entwickler-zustaende.html` — developer-only state reference

## Global rules
- Global Search: empty until real indexed data exists.
- Notifications: empty until real actionable events exist.
- Datenqualität: `Nicht verfügbar` until backend-owned metrics exist.
- Contract 360: no contract-specific values until a real contract is selected.
- Evidence Viewer: no evidence/facts until a real source is loaded.
- Archive: no rows until real archived contracts exist.
- Audit: no events until backend provides them.
- Costs: never display hard-coded amounts.
- Equipment: never display hard-coded device IDs.
- Backup: never display fake backup dates/statuses.
- Organization/user identity: show unavailable/unconnected until real organization/auth data is available.

## Product principle
Medflux must answer:
1. Was ist passiert?
2. Warum ist es wichtig?
3. Wo ist der Nachweis?
4. Was wurde bestätigt?
5. Was muss jetzt getan werden?

Never use demo data to make the interface look full.
