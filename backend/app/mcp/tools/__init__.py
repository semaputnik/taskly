"""
The MCP tools (spec #247). Importing this package imports every tool module
below, which is what actually registers each with `app.mcp.server.mcp_server`
(its own `@mcp_server.tool(...)`); `app.mcp.gateway` imports this package for
exactly that side effect.

Adding a tool: a new module here, `@mcp_server.tool(...)` on its function,
built from `app.mcp.conventions` rather than re-deriving any of it — a fresh
caller from `conventions.open_caller(ctx)`, ids and names resolved with
`resolve_task_id`/`resolve_project`/`resolve_tag_name`, dates with
`resolve_date`, a list rendered with `render_task_rows`/`list_result`, and
every refusal raised with `conventions.refuse` or caught and re-raised with
`conventions.refusal` — then import it below.
"""

from app.mcp.tools import (
    comment_task,
    complete_task,
    create_task,
    delete_task,
    get_task,
    list_completions,
    list_tags,
    search_activity,
    search_tasks,
    update_task,
    whoami,
)

__all__ = [
    "comment_task",
    "complete_task",
    "create_task",
    "delete_task",
    "get_task",
    "list_completions",
    "list_tags",
    "search_activity",
    "search_tasks",
    "update_task",
    "whoami",
]
