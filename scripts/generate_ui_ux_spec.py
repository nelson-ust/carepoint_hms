"""
Regenerate ``UI_UX_DESIGN_SPECIFICATION.md`` from the live FastAPI app.

The Carepoint HMS backend exposes ~700 endpoints across ~95 route files.
Maintaining the form/endpoint registry section of the design spec by hand
is impractical — it goes stale the moment a single payload changes.

This script takes the FastAPI app's ``openapi()`` output, which is the
ground truth FastAPI itself serves at ``/openapi.json``, and re-emits the
registry section of the markdown document:

    * every operation grouped by its router tag (= module),
    * for each operation: HTTP method, path, summary, a JSON-shaped
      request payload example (derived from the request body schema),
      and a JSON-shaped response example.

The preamble of the document — design language, frontend architecture,
the registry intro — is preserved verbatim. Only everything after the
``## 🗺️ 3. Master Form & Endpoint Registry`` header is rewritten.

Usage
-----
From the project root, inside the project's virtualenv::

    python scripts/generate_ui_ux_spec.py

Optional flags::

    --output PATH        write somewhere else (default: UI_UX_DESIGN_SPECIFICATION.md)
    --dry-run            print the new registry to stdout without writing
    --quiet              suppress the per-tag progress logs

Why the script needs the app's runtime
--------------------------------------
The schemas use ``from __future__ import annotations`` and reference
each other through ``$ref``. The only way to resolve everything
correctly (inheritance, forward refs, `Annotated[...]`, generated
union types) is to let FastAPI build the OpenAPI document itself.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ----------------------------------------------------------------------------
# Environment scaffolding so ``app.main`` imports cleanly even when the
# script is run on a developer laptop without a configured .env. The values
# below are only used at import time (pydantic-settings validators); no
# database connection is opened just by importing the app.
# ----------------------------------------------------------------------------
os.environ.setdefault(
    "CAREPOINT_HMS_DATABASE_URL",
    "postgresql+psycopg2://placeholder:placeholder@localhost:5432/placeholder",
)
os.environ.setdefault(
    "CAREPOINT_HMS_MASTER_DATABASE_URL",
    os.environ["CAREPOINT_HMS_DATABASE_URL"],
)
os.environ.setdefault("CAREPOINT_HMS_SECRET_KEY", "x" * 48)
os.environ.setdefault("CAREPOINT_HMS_DATABASE_ENCRYPTION_KEY", "y" * 48)
os.environ.setdefault("CAREPOINT_HMS_ENVIRONMENT", "development")


SPEC_PATH = ROOT / "UI_UX_DESIGN_SPECIFICATION.md"
REGISTRY_HEADER = "## 🗺️ 3. Master Form & Endpoint Registry"
REGISTRY_INTRO = (
    "This section is **auto-generated** from the live FastAPI app's OpenAPI "
    "schema by ``scripts/generate_ui_ux_spec.py`` — do not edit by hand. "
    "Every form and page in the system is mapped here to the exact HTTP "
    "method, path, request payload, and response shape that the API expects "
    "and returns.\n"
)


# ----------------------------------------------------------------------------
# JSON-Schema → example value
# ----------------------------------------------------------------------------

# Limit recursion depth so cyclic schemas (rare but they exist when models
# reference each other through optional FKs) don't blow the stack.
_MAX_DEPTH = 6


def _resolve_ref(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref") or ""
    if not ref:
        return schema
    name = ref.rsplit("/", 1)[-1]
    return components.get(name, {})


def schema_to_example(
    schema: dict[str, Any] | None,
    components: dict[str, Any],
    depth: int = 0,
) -> Any:
    """
    Render an OpenAPI/JSON-Schema fragment as a small example value.

    The intent is "what does this field look like over the wire", not a
    fully realistic payload — placeholders ("string", 0, false, ...) are
    fine, matching the style of the existing spec.
    """
    if schema is None or depth > _MAX_DEPTH:
        return None

    # Resolve $ref against the schemas component bucket.
    if "$ref" in schema:
        return schema_to_example(_resolve_ref(schema, components), components, depth + 1)

    # Union types — pick the first non-null branch (matches Pydantic's
    # Optional[X] = X | None layout in OpenAPI 3.1).
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            if branch.get("type") != "null":
                return schema_to_example(branch, components, depth + 1)
        return None
    if "oneOf" in schema:
        return schema_to_example(schema["oneOf"][0], components, depth + 1)

    # allOf — merge property maps from each branch and recurse.
    if "allOf" in schema:
        merged: dict[str, Any] = {"type": "object", "properties": {}}
        for branch in schema["allOf"]:
            resolved = _resolve_ref(branch, components) if "$ref" in branch else branch
            merged["properties"].update(resolved.get("properties", {}))
        return schema_to_example(merged, components, depth + 1)

    # Enums beat type — emit the first allowed value.
    if "enum" in schema:
        return schema["enum"][0]

    # Explicit example wins when the schema author provided one.
    if "example" in schema:
        return schema["example"]
    if "default" in schema and schema.get("type") not in ("object", "array"):
        return schema["default"]

    t = schema.get("type")
    if t == "object" or "properties" in schema:
        return {
            k: schema_to_example(v, components, depth + 1)
            for k, v in schema.get("properties", {}).items()
        }
    if t == "array":
        return [schema_to_example(schema.get("items", {}), components, depth + 1)]
    if t == "boolean":
        return False
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "string":
        fmt = schema.get("format")
        return {
            "date-time": "YYYY-MM-DDTHH:MM:SSZ",
            "date": "YYYY-MM-DD",
            "time": "HH:MM:SS",
            "email": "user@example.com",
            "uuid": "00000000-0000-0000-0000-000000000000",
            "binary": "<binary>",
        }.get(fmt or "", "string")

    return None


# ----------------------------------------------------------------------------
# Markdown rendering
# ----------------------------------------------------------------------------

_METHOD_ORDER = ("get", "post", "put", "patch", "delete")


def _operation_summary(op: dict[str, Any], method: str, path: str) -> str:
    return op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, default=str) + "\n```"


def render_registry(openapi: dict[str, Any]) -> str:
    """Render the entire endpoint registry section as markdown."""
    components: dict[str, Any] = openapi.get("components", {}).get("schemas", {})
    paths: dict[str, Any] = openapi.get("paths", {})

    by_tag: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for path, ops in paths.items():
        for method, op in ops.items():
            if method not in _METHOD_ORDER:
                continue
            tag = (op.get("tags") or ["Untagged"])[0]
            by_tag.setdefault(tag, []).append((method, path, op))

    out: list[str] = []
    for tag in sorted(by_tag):
        operations = by_tag[tag]
        # Stable order within a module: by path then by HTTP method.
        operations.sort(key=lambda triple: (triple[1], _METHOD_ORDER.index(triple[0])))

        out.append(f"### 📦 Module: {tag}")
        out.append("")

        for method, path, op in operations:
            out.append(f"#### Form/Action: {_operation_summary(op, method, path)}")
            out.append(f"- **Endpoint**: `{method.upper()} {path}`")

            description = op.get("description")
            if description:
                # Keep markdown tidy — fold the description onto one line.
                folded = " ".join(description.strip().splitlines())
                out.append(f"- **Description**: {folded}")

            # Request body — only JSON content is rendered (the spec is
            # JSON-only and any multipart endpoints are intentionally
            # marked as such by FastAPI's media type).
            req_schema = (
                op.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            if req_schema:
                out.append("")
                out.append("**Request Payload:**")
                out.append(_json_block(schema_to_example(req_schema, components)))

            # Pick the first 2xx response that carries a JSON body.
            response_rendered = False
            for code in ("200", "201", "202"):
                resp = op.get("responses", {}).get(code)
                if not resp:
                    continue
                resp_schema = (
                    resp.get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                if not resp_schema:
                    continue
                out.append("")
                out.append(f"**Response Body** (`{code}`):")
                out.append(_json_block(schema_to_example(resp_schema, components)))
                response_rendered = True
                break

            if not response_rendered:
                # 204 No Content or non-JSON response — note it explicitly.
                two_xx = next(
                    (
                        code
                        for code in ("204", "200", "201", "202")
                        if code in op.get("responses", {})
                    ),
                    None,
                )
                if two_xx:
                    out.append("")
                    out.append(f"**Response**: `{two_xx}` (no JSON body)")

            out.append("")
            out.append("---")
            out.append("")

    return "\n".join(out)


# ----------------------------------------------------------------------------
# Document assembly + entry point
# ----------------------------------------------------------------------------


def assemble_document(openapi: dict[str, Any], existing_text: str) -> str:
    """
    Combine the preserved preamble with a freshly rendered registry.
    """
    idx = existing_text.find(REGISTRY_HEADER)
    if idx == -1:
        preamble = existing_text.rstrip() + "\n\n"
    else:
        preamble = existing_text[:idx]

    registry = render_registry(openapi)
    return (
        f"{preamble}{REGISTRY_HEADER}\n\n"
        f"{REGISTRY_INTRO}\n"
        "---\n\n"
        f"{registry}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=SPEC_PATH,
        help="Markdown file to write (default: UI_UX_DESIGN_SPECIFICATION.md).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the new registry to stdout instead of writing the file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logs.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if not args.quiet:
        print("Importing FastAPI app... (this can take a few seconds)")

    # Defer the heavy import so --help doesn't pay for it.
    from app.main import app  # noqa: WPS433 — intentional late import

    if not args.quiet:
        print("Building OpenAPI schema...")
    openapi = app.openapi()

    if args.dry_run:
        print(render_registry(openapi))
        return

    existing = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
    new_doc = assemble_document(openapi, existing)
    args.output.write_text(new_doc, encoding="utf-8")

    total_ops = sum(
        1
        for ops in openapi.get("paths", {}).values()
        for method in ops
        if method in _METHOD_ORDER
    )
    total_tags = len({(op.get("tags") or ["Untagged"])[0]
                      for ops in openapi.get("paths", {}).values()
                      for method, op in ops.items()
                      if method in _METHOD_ORDER})

    if not args.quiet:
        print(
            f"Wrote {args.output} — {total_ops} endpoints across {total_tags} modules."
        )


if __name__ == "__main__":
    main()
