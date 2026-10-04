# Usability test script (5 users per round)

Run before the refactoring (baseline) and after each major phase. 45 minutes per person, think-aloud, screen recording only with consent. Test environment: the e2e test database (no real contracts).

## Participants
- 2 × contract managers (daily users)
- 1 × reviewer / controller
- 1 × admin (IT or Einkauf)
- 1 × occasional user (e.g. head of a department, read-only)

## Tasks (measure time, success, errors, hints needed)

| # | Task (read aloud) | Success criterion |
|---|---|---|
| 1 | "Which contracts can be cancelled in the next 90 days?" | correct list within 60 s |
| 2 | "Who is responsible for the CT maintenance contract, and when must it be cancelled at the latest?" | both answers correct |
| 3 | "Add the internal number INT-4711 to the PACS contract." | saved, value visible |
| 4 | "Create a reminder to request a new offer in two weeks." | deadline exists with correct date |
| 5 | "Which contracts mention a 24/7 hotline? Show me the page." | correct document page opened |
| 6 | "How much do we spend per year with Siemens?" | correct amount |
| 7 | "Export the contracts of the Radiologie department to Excel." | file downloaded with correct rows |
| 8 (admin) | "Give a new colleague read-only access." | user and role set correctly |

## After the session
- SUS questionnaire (10 items, German version).
- Three open questions: What was most confusing? What did you miss? What would you use every day?

## Targets
- Task success ≥ 90 %, median time per task ≤ baseline − 30 %, SUS ≥ 80.
