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
    f"POST {API}/activity-log/{{entry_id}}/restore",
}

LATER = "Logged once semaputnik/taskly#36 records projects, comments and attachments"
ACCOUNT = "Account and sign-in, not a change to the tasks and projects the log covers"

NOT_LOGGED = {
    f"POST {API}/projects/": LATER,
    f"PATCH {API}/projects/{{project_id}}": LATER,
    f"DELETE {API}/projects/{{project_id}}": LATER,
    f"POST {API}/tasks/{{task_id}}/comments/": LATER,
    f"PATCH {API}/comments/{{comment_id}}": LATER,
    f"DELETE {API}/comments/{{comment_id}}": LATER,
    f"POST {API}/tasks/{{task_id}}/attachments/": LATER,
    f"DELETE {API}/attachments/{{attachment_id}}": LATER,
    f"POST {API}/projects/{{project_id}}/archive": (
        "Archiving is a toggle outside the log and the restore flow (FR-05.10)"
    ),
    f"POST {API}/projects/{{project_id}}/unarchive": (
        "Archiving is a toggle outside the log and the restore flow (FR-05.10)"
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
