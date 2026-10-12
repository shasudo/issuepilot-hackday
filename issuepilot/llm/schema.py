from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_REF_PREFIX = "#/$defs/"


def flatten_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a minimal equivalent of the model's JSON schema.

    Hosted Gemma rejects pydantic-style schemas on real prompts: $refs
    500 and title/description metadata hangs generation. The stripped
    inline form (types + structure only) works in seconds, so nodes send
    it and validate the result back into the Pydantic model. The prompt
    text already explains every field, so nothing is lost.
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
                rest = {
                    key: _inline(value)
                    for key, value in node.items()
                    if key not in ("$ref", "title", "description")
                }
                return {**base, **rest}
            merged = {
                key: value for key, value in node.items() if key not in ("title", "description")
            }
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


def bind_structured(model, schema: dict):
    """Bind a flat schema with native JSON-schema enforcement.

    The method is explicit (never the provider default): OpenAI and
    Anthropic default to function calling, which requires a top-level
    title that our Gemma-safe stripped schemas deliberately omit.
    OpenAI-shaped models (including OpenRouter) additionally need the
    {"name", "schema"} wrapper; Google/Anthropic take the raw dict.
    """
    from langchain_openai import ChatOpenAI

    if isinstance(model, ChatOpenAI):
        payload = {"name": "structured_response", "schema": schema, "strict": False}
    else:
        payload = schema
    return model.with_structured_output(payload, method="json_schema")
