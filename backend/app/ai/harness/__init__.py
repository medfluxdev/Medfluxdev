"""Provider-neutral Contract Intelligence Harness.

Engine selection is explicit and provider-neutral. ``v3`` is the production
default so scanned/image-heavy PDFs can use bounded local vision. ``v2``
remains available as a text-oriented compatibility engine.
"""


def get_harness_class(settings):
    """Return the harness class for the configured ``harness_engine``."""
    engine = getattr(settings, "harness_engine", "v3") or "v3"
    # Stale pre-Vision installations may still carry HARNESS_ENGINE=v2 in a
    # private .env. Treat that historical value as the safe current default.
    # The legacy engine now requires an explicit compatibility opt-in.
    if engine in {"v2-compat", "legacy-v2"}:
        from app.ai.harness.pipeline import HarnessV2
        return HarnessV2
    from app.ai.harness.v3 import HarnessV3
    return HarnessV3