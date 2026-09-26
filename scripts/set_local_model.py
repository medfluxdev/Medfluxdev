"""Local-only selection persistence for the MedFlux local launcher.

Writes the chosen local model through the app's own persistence function
(``set_ai_selection``), which is exactly what the admin UI / API does when the
operator picks a model. It never touches database schema, credentials or
connection settings, and it never changes authentication or TLS behaviour.

Run with the backend venv Python from the backend working directory so that the
app's ``.env`` DATABASE_URL is resolved normally.

Exit codes:
  0  selection persisted (or unchanged)
  2  app could not be imported (wrong venv / cwd)
  3  database write failed (DB not migrated / unreachable)
"""

from __future__ import annotations

import os
import sys

PROVIDER_ID = "ollama"


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("[ERROR] No model name provided to set_local_model.py.")
        return 4
    model = sys.argv[1].strip()
    if model == "KEEP":
        print("[INFO] Keeping the existing MedFlux model selection.")
        return 0

    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
    backend_dir = os.path.normpath(backend_dir)
    if os.path.isdir(os.path.join(backend_dir, "app")) and backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    try:
        from app.database.ai_selection import get_ai_selection, set_ai_selection
    except Exception as exc:  # noqa: BLE001
        print(f"[WARNING] Could not import app (backend venv?): {exc}")
        return 2

    try:
        current = get_ai_selection()
        if current[0] == PROVIDER_ID and current[1] == model:
            print(f"[OK] MedFlux is already configured for {PROVIDER_ID}/{model}.")
            return 0
        set_ai_selection(PROVIDER_ID, model)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARNING] Could not persist model selection (DB reachable/migrated?): {exc}")
        print("[WARNING] Start MedFlux and select the model once in the UI instead.")
        return 3

    print(f"[OK] MedFlux configured to use local model: {PROVIDER_ID}/{model}.")
    print("[INFO] Provider is pinned to the LOCAL Ollama server; no cloud provider is configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())