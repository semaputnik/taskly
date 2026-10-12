"""
Guards the `app/models.py` -> `app/models/` package split (#280, parent #275).

FastAPI names an OpenAPI schema after its Python class, and only falls back
to a module-qualified name when two distinct classes collide on the same
one. `app/models.py` becoming a package of domain modules (#280) is exactly
the change that could introduce such a collision — two domain modules each
defining a class of the same name, both still reachable through
`app/models/__init__.py`'s re-exports and both used somewhere as a request or
response model. A collision renames schemas in `openapi.json`, which renames
the generated TypeScript types in `frontend/src/client`
(`frontend/openapi-ts.config.ts`, `scripts/generate-client.sh`) and breaks
every frontend import of them.

This cannot be caught by inspecting the live `app.models` namespace: Python
silently keeps only the last definition or import of a given name, so by the
time the module has finished loading, two classes can never appear to share
a name there even if their source does. Instead this parses the source
directly — `app/models.py` today, every `*.py` file in `app/models/` once
#280 lands — and compares every top-level class name across all of it,
which is what actually determines whether two distinct class objects exist
with the same name.
"""

import ast
import glob
import os
from collections import Counter

import app.models as models_module


def _source_files() -> list[str]:
    package_path = getattr(models_module, "__path__", None)
    if package_path is not None:
        # The shape #280 moves to: every module the package holds.
        return sorted(
            file
            for package_dir in package_path
            for file in glob.glob(os.path.join(package_dir, "*.py"))
        )
    # The current shape: one file.
    assert models_module.__file__ is not None
    return [models_module.__file__]


def test_no_two_model_classes_share_a_name() -> None:
    names: list[str] = []
    for file in _source_files():
        with open(file, encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=file)
        names.extend(
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        )

    duplicates = {name for name, count in Counter(names).items() if count > 1}
    assert not duplicates, (
        f"these class names are defined more than once across app/models: "
        f"{sorted(duplicates)}. FastAPI only falls back to a module-qualified "
        "schema name when two distinct classes collide on the same name — a "
        "collision here would rename schemas in openapi.json and the "
        "generated TypeScript types that depend on them."
    )
