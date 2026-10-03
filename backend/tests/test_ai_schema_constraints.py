from app.ai.schema import normalize_constrained_schema, strip_json_code_fence


def test_annotation_only_leaf_is_given_permissive_json_types():
    schema = {
        "type": "object",
        "properties": {"value": {"title": "Value"}},
    }

    normalized = normalize_constrained_schema(schema)

    assert normalized["properties"]["value"] == {
        "title": "Value",
        "type": ["object", "array", "string", "number", "boolean", "null"],
    }


def test_schema_references_are_inlined_before_constraint_normalization():
    schema = {
        "type": "object",
        "$defs": {"LooseValue": {"title": "Value"}},
        "properties": {"value": {"$ref": "#/$defs/LooseValue"}},
    }

    normalized = normalize_constrained_schema(schema)

    assert "$defs" not in str(normalized)
    assert "$ref" not in str(normalized)
    assert normalized["properties"]["value"]["type"] == [
        "object", "array", "string", "number", "boolean", "null"
    ]


def test_schema_normalization_does_not_mutate_input_or_valid_subschemas():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "title": "Name"},
            "value": {"title": "Value"},
        },
    }
    original = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "title": "Name"},
            "value": {"title": "Value"},
        },
    }

    normalized = normalize_constrained_schema(schema)

    assert schema == original
    assert normalized["properties"]["name"] == {"type": "string", "title": "Name"}


def test_json_response_code_fence_is_removed_only_when_it_wraps_the_whole_payload():
    payload = '{"facts": []}'

    assert strip_json_code_fence(f"```json\n{payload}\n```") == payload
    assert strip_json_code_fence(f"```\n{payload}\n```") == payload
    assert strip_json_code_fence(payload) == payload
    assert strip_json_code_fence(f"prefix\n```json\n{payload}\n```") == (
        f"prefix\n```json\n{payload}\n```"
    )
