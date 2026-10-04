from pathlib import Path


def test_intelligence_router_registered():
    source = (Path(__file__).parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "intelligence" in source
    assert "app.include_router(intelligence.router)" in source
