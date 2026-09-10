"""Provider-neutral Contract Intelligence Harness.

Engine selection is explicit and provider-neutral. ``v2`` (v2.1) remains the
production default until real ABIOMED/Accutron benchmarks validate ``v3``.
"""


def get_harness_class(settings):
    """Return the harness class for the configured ``harness_engine``."""
    engine = getattr(settings, "harness_engine", "v2") or "v2"
    if engine == "v3":
        from app.ai.harness.v3 import HarnessV3
        return HarnessV3
    from app.ai.harness.pipeline import HarnessV2
    return HarnessV2