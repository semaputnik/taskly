"""
The MCP server mounted at `/mcp` (spec #247, #252, ADR-0012): the same
Taskly a bot user already reaches over the REST API, read by an agent as a
small set of tools instead of routes.

- `app.mcp.gateway` — the ASGI boundary, session-to-token binding, and the
  `mount`/`run` `app.main` calls (re-exported here, since that is all
  `app.main` needs of this package).
- `app.mcp.server` — the one `MCPServer` instance every tool registers on.
- `app.mcp.conventions` — the argument, output and refusal rules every tool
  follows (spec #247, settled by #253): a caller per call, ids and names
  resolved, dates read, lists rendered, refusals reported.
- `app.mcp.tools` — one module per tool (or small group), imported for its
  registration side effect by `app.mcp.gateway`. A new tool is a new module
  there, importing from `app.mcp.conventions` rather than re-deriving any of
  it; nothing here or in `app.mcp.gateway` changes to add one.
"""

from app.mcp.gateway import MCP_PATH, mount, run

__all__ = ["MCP_PATH", "mount", "run"]
