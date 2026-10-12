from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_REF_PREFIX = "#/$defs/"


def flatten_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return the model's JSON schema with $defs inlined.

    Hosted Gemma rejects pydantic-style $ref schemas on real prompts
    (500 INTERNAL) while accepting the equivalent inline schema, so
    nodes send the flattened form and validate the result back into
    the Pydantic model. Semantically identical for validation.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def _resolve(ref: str) -> Any:
        assert ref.startswith(_REF_PREFIX), f"unexpected ref: {ref}"
        return _inline(defs[ref[len(_REF_PREFIX):]])

    def _inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                base = _resolve(node["$ref"])
                assert isinstance(base, dict)
                rest = {key: _inline(value) for key, value in node.items() if key != "$ref"}
                return {**base, **rest}
            merged = dict(node)
            nested = merged.pop("allOf", None)
            if isinstance(nested, list) and len(nested) == 1 and isinstance(nested[0], dict) and "$ref" in nested[0]:
                base = _resolve(nested[0]["$ref"])
                assert isinstance(base, dict)
                merged = {**base, **{key: _inline(value) for key, value in merged.items()}}
                return merged
            return {key: _inline(value) for key, value in merged.items()}
        if isinstance(node, list):
            return [_inline(value) for value in node]
        return node

    return _inline(schema)
