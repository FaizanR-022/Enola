"""Write the API's OpenAPI schema to a file without starting a server.

    python -m enola.scripts.export_openapi web/openapi.json

The web app turns this into TypeScript types (`npm run gen:api`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from enola.api.main import create_app

ALWAYS_COMPLETE_SUFFIXES = ("Read", "Summary", "Hit", "Candidate", "Row", "Item", "Owner", "HealthResponse", "HeldCount", "ToolInfo")


def mark_reads_complete(schema: dict[str, Any]) -> None:
    """Response models always carry every field, even ones with defaults. Pydantic's
    OpenAPI marks defaulted fields optional, which would force `?? ""` all over the
    web app; here we say what is true instead."""
    for name, component in schema.get("components", {}).get("schemas", {}).items():
        if name.endswith(ALWAYS_COMPLETE_SUFFIXES) or name.startswith("Page_"):
            props = component.get("properties")
            if isinstance(props, dict) and props:
                component["required"] = list(props)


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "web/openapi.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = create_app().openapi()
    mark_reads_complete(schema)
    target.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
