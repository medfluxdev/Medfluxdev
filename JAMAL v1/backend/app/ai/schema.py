"""JSON-Schema aus den Pydantic-Vertragsmodellen für native strukturierte Ausgabe.

Ollamas /api/chat erwartet als `format` ein EIGENSTÄNDIGES (selbstenthaltenes)
JSON-Schema ohne `$ref`/`$defs`-Verweise (empirisch geprüft, STEP 8B). Dieses
Modul leitet ein solches Schema determiniert aus dem bestehenden Pydantic-
Modell `Contract` ab – es wird KEIN zweites, manuell gepflegtes Schema gepflegt.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.models.contract import Contract


def _deref(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """Ersetzt rekursiv alle `$ref`-Verweise durch ihre Definition (inline)."""
    if isinstance(schema, list):
        return [_deref(item, defs) for item in schema]
    if not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "$ref":
            return _deref(defs[value.split("/")[-1]], defs)
        if key in ("$defs", "definitions"):
            continue  # Definitionen werden inline gezogen, nicht mitgeführt
        out[key] = _deref(value, defs)
    return out


def pydantic_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Liefert ein selbstenthaltenes JSON-Schema für ein Pydantic-Modell.

    Das Schema ist deterministisch aus `model.model_json_schema()` abgeleitet;
    `$ref`/`$defs` werden inline aufgelöst (Ollama akzeptiert keine Verweise).
    `date`-Felder werden auf `{"type": "string", "format": "date"}` abgebildet
    (ISO YYYY-MM-DD) und sind mit `null` nullable, damit Fehlangaben als null
    und nicht als erfundenes Datum abgegeben werden können.
    """
    raw = model.model_json_schema()
    defs: dict[str, Any] = dict(raw.get("$defs", {}))
    schema = {k: v for k, v in raw.items() if k not in ("$defs", "definitions")}
    return _deref(schema, defs)


def contract_json_schema() -> dict[str, Any]:
    """Liefert ein selbstenthaltenes JSON-Schema für `Contract`."""
    return pydantic_json_schema(Contract)


def compact_contract_json_schema() -> str:
    """Kompakte JSON-Repräsentation des selbstenthaltenen Schemas (für Tests/Logging)."""
    import json

    return json.dumps(contract_json_schema(), sort_keys=True, ensure_ascii=False)
