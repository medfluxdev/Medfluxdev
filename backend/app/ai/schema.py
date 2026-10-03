"""JSON-Schema aus den Pydantic-Vertragsmodellen für native strukturierte Ausgabe.

Ollamas /api/chat erwartet als `format` ein EIGENSTÄNDIGES (selbstenthaltenes)
JSON-Schema ohne `$ref`/`$defs`-Verweise (empirisch geprüft, STEP 8B). Dieses
Modul leitet ein solches Schema deterministisch aus dem bestehenden Pydantic-
Modell `Contract` ab – es wird KEIN zweites, manuell gepflegtes Schema gepflegt.

Zusätzlich normalisiert `normalize_constrained_schema` beliebige Pydantic-
Schemas für die grammatikbasierte Decodierung: Ollama lehnt jedes Teilschema ab,
das ausschließlich Annotationsschlüssel (`title`, `default`, `description`)
enthält und keinen strukturellen Typ trägt. Pydantic rendert genau so ein Feld
vom Typ `Any` (z. B. `{"title": "Value"}`), was ohne Normalisierung mit HTTP 500
`invalid JSON schema in format` endet. Die Validierungssemantik bleibt dabei
unverändert: das permissive Blatt wird nur ergänzt, die Pydantic-Prüfung des
Antwortmodells entscheidet weiterhin über Annahme oder Ablehnung.
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel

from app.models.contract import Contract

_STRUCTURAL_KEYWORDS = frozenset(
    {
        "$ref",
        "additionalProperties",
        "allOf",
        "anyOf",
        "const",
        "enum",
        "items",
        "oneOf",
        "prefixItems",
        "properties",
        "required",
        "type",
    }
)

# Erlaubt jeden JSON-Wert. Die fachliche Prüfung bleibt beim Antwortmodell;
# insbesondere darf `Any` auch strukturierte Vertragswerte (Objekte/Arrays) liefern.
_PERMISSIVE_LEAF: dict[str, Any] = {
    "type": ["object", "array", "string", "number", "boolean", "null"]
}


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


def _constrain(node: Any) -> Any:
    """Sorgt rekursiv dafür, dass jedes Teilschema einen Typ trägt.

    Nur Teilschemas *innerhalb* von `properties`/`items`/`anyOf`/... werden
    bearbeitet; die Wurzel und verschachtelte `properties`-Container bleiben
    unangetastet.
    """
    if isinstance(node, list):
        return [_constrain(item) for item in node]
    if not isinstance(node, dict):
        return node

    for container in ("properties", "$defs", "definitions"):
        block = node.get(container)
        if isinstance(block, dict):
            for name, sub in block.items():
                block[name] = _constrain(sub)
    for key in ("items", "additionalProperties", "contains"):
        if isinstance(node.get(key), dict):
            node[key] = _constrain(node[key])
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        if isinstance(node.get(key), list):
            node[key] = _constrain(node[key])

    if not (_STRUCTURAL_KEYWORDS & set(node)):
        node.update(copy.deepcopy(_PERMISSIVE_LEAF))
    return node


def normalize_constrained_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Macht ein Pydantic-Schema für Ollamas `format`-Decoder nutzbar.

    Ollama lehnt jedes Teilschema ab, das nur Annotationsschlüssel trägt und
    keinen strukturellen Typ (z. B. das von Pydantic für `Any` erzeugte
    `{"title": "Value"}`) mit HTTP 500 `invalid JSON schema in format` ab.
    Der Decoder unterstützt außerdem keine `$ref`/`$defs`; diese werden vor
    der Normalisierung inline aufgelöst. Solche Blätter erhalten ein
    permissives Typ-Union für alle JSON-Werttypen; alle übrigen Schlüssel –
    auch `title`, `default`, `enum`, `maxLength` – bleiben erhalten. Das
    Eingabedict wird nicht verändert.
    """
    copied = copy.deepcopy(schema)
    defs = dict(copied.get("$defs", copied.get("definitions", {})))
    without_defs = {
        key: value
        for key, value in copied.items()
        if key not in ("$defs", "definitions")
    }
    return _constrain(_deref(without_defs, defs))


def contract_json_schema() -> dict[str, Any]:
    """Liefert ein selbstenthaltenes JSON-Schema für `Contract`."""
    return pydantic_json_schema(Contract)


def compact_contract_json_schema() -> str:
    """Kompakte JSON-Repräsentation des selbstenthaltenen Schemas (für Tests/Logging)."""
    import json

    return json.dumps(contract_json_schema(), sort_keys=True, ensure_ascii=False)
