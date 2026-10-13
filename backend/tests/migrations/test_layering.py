"""
A lint rule rather than a convention (#303): nothing below `app.api` may
import from it, so the next inversion fails a test instead of landing the
way `app.tasks` and `app.comments` importing `app.api.access` did (named in
#296, fixed here by moving the access rules to `app.access`).

`app.api` (REST routes and `app.api.deps`) and `app.mcp` (the MCP tools and
gateway, ADR-0012) are this app's two front doors: both call down into the
operations (`app.tasks`, `app.comments`), access (`app.access`), repository
and model layers, and `app.mcp` legitimately reaches into `app.api` itself
for some of what it shares with the REST surface (`app.api.deps.Caller`,
a route function reused as-is). `app.main` wires both into one FastAPI app.
Everything else in `app` sits below that line and may not import back up
into `app.api`.

Parses the source directly, the same way `test_models_class_names.py` checks
for class-name collisions: a static walk over the `ast` finds every import
regardless of whether the module importing it is ever exercised by a test,
which a runtime check of `sys.modules` would not.
"""

import ast
import glob
import os

import app

APP_ROOT = os.path.dirname(app.__file__)

# This app's two front doors, and the module that wires them into one
# FastAPI app. Nothing else under `app/` may import from `app.api`.
ABOVE_THE_LINE = ("app.api", "app.mcp", "app.main")


def _module_name(file: str) -> str:
    relative = os.path.relpath(file, APP_ROOT)
    if os.path.basename(relative) == "__init__.py":
        relative = os.path.dirname(relative)
    else:
        relative = relative[: -len(".py")]
    dotted = relative.replace(os.sep, ".")
    return f"app.{dotted}" if dotted else "app"


def _is_above_the_line(module_name: str) -> bool:
    return any(
        module_name == name or module_name.startswith(f"{name}.")
        for name in ABOVE_THE_LINE
    )


def _app_api_imports(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "app.api" or node.module.startswith("app.api."):
                found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app.api" or alias.name.startswith("app.api."):
                    found.append(alias.name)
    return found


def _source_files() -> list[str]:
    return sorted(glob.glob(os.path.join(APP_ROOT, "**", "*.py"), recursive=True))


def test_nothing_below_app_api_imports_from_it() -> None:
    violations: dict[str, list[str]] = {}
    for file in _source_files():
        module_name = _module_name(file)
        if _is_above_the_line(module_name):
            continue
        with open(file, encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=file)
        imports = _app_api_imports(tree)
        if imports:
            violations[module_name] = imports

    assert not violations, (
        "these modules sit below app.api but import from it, an upward "
        f"dependency the layering forbids: {violations}"
    )
