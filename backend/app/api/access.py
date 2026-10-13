"""
`app/access.py`, re-exported here (#303): the access rules — scope, grants,
the archive, ownership — read like `app.api`'s own because every route
reaches them, but they are domain rules, not HTTP ones, and `app.tasks` /
`app.comments` (the operations layer, below `app.api`) need them too. Moved
below `app.api` the same way `Caller` was in #282, so the operations import
them without reaching up into the layer that calls them.

Every name below is unchanged: this re-exports the whole of `app.access` so
none of its other importers — every route, every MCP tool, `tests/access/` —
has to move with it.
"""

from app.access import (
    BOT_REFUSED_STATUS,
    COMMENT_BY_BOT_CODE,
    COMMENT_BY_BOT_STATUS,
    OUTSIDE_SCOPE_CODE,
    PERMISSION_NOT_GRANTED_CODE,
    PROJECT_ARCHIVED_CODE,
    PROJECT_ARCHIVED_STATUS,
    TASK_NOT_FOUND,
    TaskAccess,
    TaskAction,
    activity_log_scope,
    archived_refusal,
    authorize_activity_log,
    authorize_tag_creation,
    authorize_tag_names,
    authorize_tasks,
    bot_reaches_project,
    bot_reaches_task,
    get_attachment,
    get_comment,
    get_project,
    get_task,
    get_tasks,
    refuse_archived_for_bot,
    require_project_writable,
)

__all__ = [
    "BOT_REFUSED_STATUS",
    "COMMENT_BY_BOT_CODE",
    "COMMENT_BY_BOT_STATUS",
    "OUTSIDE_SCOPE_CODE",
    "PERMISSION_NOT_GRANTED_CODE",
    "PROJECT_ARCHIVED_CODE",
    "PROJECT_ARCHIVED_STATUS",
    "TASK_NOT_FOUND",
    "TaskAccess",
    "TaskAction",
    "activity_log_scope",
    "archived_refusal",
    "authorize_activity_log",
    "authorize_tag_creation",
    "authorize_tag_names",
    "authorize_tasks",
    "bot_reaches_project",
    "bot_reaches_task",
    "get_attachment",
    "get_comment",
    "get_project",
    "get_task",
    "get_tasks",
    "refuse_archived_for_bot",
    "require_project_writable",
]
