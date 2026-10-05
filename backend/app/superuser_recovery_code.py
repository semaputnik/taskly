"""
Print a recovery code for the superuser (FR-12.19).

The superuser recovers their account from the server, since nobody above them
can issue them a code from the interface. The code is spent on the sign-in
screen like any other, and it is also how an installation upgraded from
password sign-in gives its superuser a first passkey (ADR-0007).

    python -m app.superuser_recovery_code
"""

import sys

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.passkeys import find_superuser, issue_recovery_code


def main() -> int:
    with Session(engine) as session:
        superuser = find_superuser(session)
        if superuser is None:
            sys.stderr.write(
                "This installation has no superuser yet. Register the address "
                f"{settings.FIRST_SUPERUSER} on the sign-in screen to become it.\n"
            )
            return 1
        email = superuser.email
        issued = issue_recovery_code(session, user=superuser)
    sys.stdout.write(
        f"Recovery code for {email}: {issued.code}\n"
        f"It expires at {issued.expires_at:%Y-%m-%d %H:%M} UTC. Enter it with "
        "this email under “Have a recovery code?” on the sign-in screen.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
