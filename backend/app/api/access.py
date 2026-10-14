"""
`app/access.py`, re-exported here (#303): the access rules — scope, grants,
the archive, ownership — read like `app.api`'s own because every route
reaches them, but they are domain rules, not HTTP ones, and `app.tasks` /
`app.comments` (the operations layer, below `app.api`) need them too. Moved
below `app.api` the same way `Caller` was in #282, so the operations import
them without reaching up into the layer that calls them.

Every name below is unchanged: this re-exports the whole of `app.access` so
none of its other importers — every route, every MCP tool, `tests/access/` —
has to move with it. The status and code constants this used to re-export
(`PROJECT_ARCHIVED_CODE` and its five siblings) are gone (#309): every
refusal `app.access` gives is now one of `app.refusals`'s own values, built
by a function there rather than assembled from a status and a code a caller
had to import separately — nothing outside `app.access` imported these
constants, so none of them needed a replacement.
"""

from app.access import (
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
    narrowing_project,
    narrowing_task,
    refuse_archived_for_bot,
    require_project_writable,
)

__all__ = [
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
    "narrowing_project",
    "narrowing_task",
    "refuse_archived_for_bot",
    "require_project_writable",
]
