"""
A lint rule rather than a convention (#303): nothing below `app.api` may
import from it, so the next inversion fails a test instead of landing the
way `app.tasks` and `app.comments` importing `app.api.access` did (named in
#296, fixed here by moving the access rules to `app.access`).

`app.api` (REST routes and `app.api.deps`) and `app.mcp` (the MCP tools and
gateway, ADR-0012) are this app's two front doors: both call down into the
operations (`app.tasks`, `app.comments`), access (`app.access`), repository
and model layers. `app.mcp` also legitimately reaches across into `app.api`
itself for pieces it shares with the REST surface rather than duplicating —
`app.api.deps.Caller` and `get_mcp_caller`, the re-exported `app.api.access`
shim some tools still import by that name, and a route function reused as-is
(`app.api.routes.caller.read_caller`, by `whoami`). None of that is the
inversion this test exists to catch: a
front door reaching sideways into the other front door is not a lower layer
reaching up into one. `app.main` wires both into one FastAPI app. Everything
else in `app` sits below that line and may not import back up into
`app.api`.

A second rule lives here too (#322): nothing below `app.api` may raise
`fastapi.HTTPException` either — an operation, `app.access` and (since #309)
`app.activity_log` all answer in `app.refusals.Refusal`, which knows nothing
about HTTP, so an `HTTPException` surfacing from any of them is the same
inversion as an import, caught the same way: statically, so the next one
fails a test rather than leaving a non-HTTP caller (`app.mcp`) catching an
HTTP-shaped exception to learn it was refused the way `app.activity_log`'s
own task/project narrowing used to (#322, following #309's report).

Parses the source directly, the same way `test_models_class_names.py` checks
for class-name collisions: a static walk over the `ast` finds every import
and every raise regardless of whether the module is ever exercised by a
test, which a runtime check of `sys.modules` would not.
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


def _raised_name(node: ast.expr | None) -> str | None:
    """
    The dotted-or-bare name a `raise` (or a `raise ... from ...`) actually
    raises, whether it names a class directly (`raise HTTPException(...)`) or
    calls one (`raise HTTPException(status_code=...)`) — the two shapes this
    codebase's own raises take, either way read off `node.exc`.
    """
    target = node
    if isinstance(target, ast.Call):
        target = target.func
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _http_exception_raises(tree: ast.AST) -> int:
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise) and _raised_name(node.exc) == "HTTPException"
    )


def test_nothing_below_app_api_raises_http_exception() -> None:
    """
    `fastapi.HTTPException` is `app.api`'s own: every refusal below it answers
    in `app.refusals.Refusal` instead (#309), `app.activity_log`'s own
    task/project narrowing included, since #322 moved its last two raises
    onto `app.access`. A module down here raising one again is the same
    inversion importing from `app.api` is — caught the same way, so the next
    one fails here rather than landing the way these two did.
    """
    violations: list[str] = []
    for file in _source_files():
        module_name = _module_name(file)
        if _is_above_the_line(module_name):
            continue
        with open(file, encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=file)
        if _http_exception_raises(tree):
            violations.append(module_name)

    assert not violations, (
        "these modules sit below app.api but raise fastapi.HTTPException, "
        f"which belongs above that line (app.refusals.Refusal instead): "
        f"{violations}"
    )
