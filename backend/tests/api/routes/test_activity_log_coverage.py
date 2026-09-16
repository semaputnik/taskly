"""
Every route that changes something is either in the activity log or listed
here as deliberately left out of it, with the reason.

The log listens at the session rather than in each route, so a new route that
changes tasks is logged without doing anything. This test is what makes that
a decision rather than an accident: a new mutating route fails it until
someone says which side it is on.
"""

from app.core.config import settings
from app.main import app

API = settings.API_V1_STR

LOGGED = {
    f"POST {API}/tasks/",
    f"PATCH {API}/tasks/{{task_id}}",
    f"DELETE {API}/tasks/{{task_id}}",
    # A batch is logged once, as the one act it was (semaputnik/taskly#66).
    f"POST {API}/tasks/bulk",
    f"POST {API}/tasks/bulk-delete",
    f"POST {API}/activity-log/{{entry_id}}/restore",
    f"POST {API}/projects/",
    f"PATCH {API}/projects/{{project_id}}",
    f"DELETE {API}/projects/{{project_id}}",
    f"POST {API}/tasks/{{task_id}}/comments/",
    f"PATCH {API}/comments/{{comment_id}}",
    # Not in FR-10.3's list, but the list is of examples and the rule is every
    # change: a deleted comment is otherwise gone without a trace.
    f"DELETE {API}/comments/{{comment_id}}",
    f"POST {API}/tasks/{{task_id}}/attachments/",
    f"DELETE {API}/attachments/{{attachment_id}}",
    f"POST {API}/tags/",
    f"PATCH {API}/tags/{{tag_id}}",
    f"DELETE {API}/tags/{{tag_id}}",
    # One entry naming both sides, not one per task or tag (semaputnik/taskly#69).
    f"POST {API}/tags/{{tag_id}}/merge",
}
ACCOUNT = "Account and sign-in, not a change to the tasks and projects the log covers"

NOT_LOGGED = {
    f"POST {API}/projects/{{project_id}}/archive": (
        "Archiving is a toggle outside the log and the restore flow (FR-05.10)"
    ),
    f"POST {API}/projects/{{project_id}}/unarchive": (
        "Archiving is a toggle outside the log and the restore flow (FR-05.10)"
    ),
    f"POST {API}/tags/duplicates/dismiss": (
        "A suggestion withheld, not a change to tags or tasks; the merge the "
        "suggestion leads to is logged"
    ),
    f"POST {API}/login/access-token": ACCOUNT,
    f"POST {API}/login/test-token": ACCOUNT,
    f"POST {API}/password-recovery/{{email}}": ACCOUNT,
    f"POST {API}/password-recovery-html-content/{{email}}": ACCOUNT,
    f"POST {API}/reset-password/": ACCOUNT,
    f"POST {API}/users/signup": ACCOUNT,
    f"PATCH {API}/users/me": ACCOUNT,
    f"PATCH {API}/users/me/password": ACCOUNT,
    f"DELETE {API}/users/me": ACCOUNT,
    f"POST {API}/bot-users/": (
        "Bot user management is not among the changes FR-10.3 covers; what a bot "
        "user does is logged, as its own actor"
    ),
    f"PATCH {API}/bot-users/{{bot_user_id}}": (
        "Bot user management is not among the changes FR-10.3 covers; what a bot "
        "user does is logged, as its own actor"
    ),
    f"DELETE {API}/bot-users/{{bot_user_id}}": (
        "Bot user management is not among the changes FR-10.3 covers; the bot "
        "user is kept, so the entries it made still name it (FR-08.19)"
    ),
    f"POST {API}/bot-users/{{bot_user_id}}/token": (
        "Issuing a token is a credential, not a change to tasks or projects"
    ),
    f"DELETE {API}/bot-users/{{bot_user_id}}/token": (
        "Revoking a token is a credential, not a change to tasks or projects"
    ),
    f"POST {API}/utils/test-email/": "Sends an email; changes nothing",
    f"POST {API}/private/users/": "Local development helper for test accounts",
}


def _mutating_routes() -> set[str]:
    return {
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in {"post", "put", "patch", "delete"}
    }


def test_every_mutating_route_is_logged_or_deliberately_left_out() -> None:
    routes = _mutating_routes()

    unclassified = routes - LOGGED - set(NOT_LOGGED)
    assert not unclassified, (
        "These routes change something but are neither in LOGGED nor in "
        f"NOT_LOGGED with a reason: {sorted(unclassified)}"
    )


def test_the_classification_names_only_routes_that_exist() -> None:
    routes = _mutating_routes()

    assert not LOGGED & set(NOT_LOGGED)
    stale = (LOGGED | set(NOT_LOGGED)) - routes
    assert not stale, f"No such routes any more: {sorted(stale)}"
