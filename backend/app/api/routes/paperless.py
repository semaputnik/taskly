from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException

from app import paperless
from app.api.deps import CurrentUser, PaperlessClientDep, SessionDep
from app.core import outbound
from app.models import (
    PaperlessConnect,
    PaperlessConnection,
    PaperlessConnectionPublic,
    PaperlessDisconnected,
    PaperlessTest,
    PaperlessTestResult,
)

# Every endpoint here takes the signed-in human: a bot user is refused with
# 403, like any endpoint that is the owner's alone (FR-04.4, FR-07.3).
router = APIRouter(prefix="/paperless", tags=["paperless"])

URL_REFUSED_STATUS = 422
TOKEN_REQUIRED_CODE = "paperless_token_required"
NOT_CONNECTED_STATUS = 404


def _public(
    session: SessionDep, user_id: Any, connection: PaperlessConnection | None
) -> PaperlessConnectionPublic:
    # No token field exists on this model: it is kept, never shown (FR-04.4).
    return PaperlessConnectionPublic(
        connected=connection is not None,
        url=connection.url if connection else None,
        documents_kept=paperless.documents_kept(session, user_id),
    )


def _refuse_address(url: str) -> None:
    try:
        outbound.check_url(url, what="Paperless address", code_prefix="paperless_url")
    except outbound.Refusal as refusal:
        raise HTTPException(
            status_code=URL_REFUSED_STATUS,
            detail={"code": refusal.code, "message": refusal.message},
        ) from refusal


def _token_required() -> HTTPException:
    return HTTPException(
        status_code=URL_REFUSED_STATUS,
        detail={
            "code": TOKEN_REQUIRED_CODE,
            "message": "Enter the API token for this address.",
        },
    )


@router.get("/", response_model=PaperlessConnectionPublic)
def read_connection(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    The caller's Paperless connection (FR-04.4): whether there is one, its
    address, and how many attachments are kept there, which is what
    disconnecting would put out of reach (FR-04.8). The token is never
    returned.
    """
    connection = paperless.get_connection(session, current_user.id)
    return _public(session, current_user.id, connection)


@router.put("/", response_model=PaperlessConnectionPublic)
def set_connection(
    *, session: SessionDep, current_user: CurrentUser, connection_in: PaperlessConnect
) -> Any:
    """
    Connect a Paperless-ngx instance, or change the connection (FR-04.4): its
    address and an API token. The address is refused, naming the rule, if it
    resolves to loopback or a private range and the installation does not
    allow those. The token is kept encrypted and only ever replaced; it may be
    left out to keep the stored one, but only while the address stays the same,
    so a token is never sent anywhere its owner did not type it for.

    Connecting moves nothing: PDFs already kept in Taskly stay there
    (FR-04.12). New PDFs go to Paperless from now on (FR-04.5).
    """
    url = paperless.normalise_url(connection_in.url)
    _refuse_address(url)
    connection = paperless.get_connection(session, current_user.id)
    now = datetime.now(UTC)
    if connection is None:
        if not connection_in.token:
            raise _token_required()
        connection = PaperlessConnection(
            user_id=current_user.id,
            url=url,
            token_encrypted=paperless.encrypt_token(connection_in.token),
        )
    else:
        if connection_in.token:
            connection.token_encrypted = paperless.encrypt_token(connection_in.token)
        elif url != connection.url:
            raise _token_required()
        connection.url = url
        connection.updated_at = now
    session.add(connection)
    paperless.restart_handovers(session, current_user.id)
    session.commit()
    session.refresh(connection)
    return _public(session, current_user.id, connection)


@router.post("/test", response_model=PaperlessTestResult)
def test_connection(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    client: PaperlessClientDep,
    test_in: Annotated[PaperlessTest | None, Body()] = None,
) -> Any:
    """
    Try a Paperless connection (FR-04.4): the saved one, or an address and
    token typed but not saved yet. It answers `ok`, or says why not; a refused
    address is a failed test, not an error. The saved token is only tried
    against the saved address.
    """
    test_in = test_in or PaperlessTest()
    saved = paperless.get_connection(session, current_user.id)
    url = paperless.normalise_url(test_in.url) if test_in.url else None
    token = test_in.token or None
    if url is None and saved is not None:
        url = saved.url
    if url is None:
        raise HTTPException(
            status_code=NOT_CONNECTED_STATUS,
            detail={
                "code": paperless.NOT_CONNECTED_CODE,
                "message": "There is no connection to test.",
            },
        )
    if token is None:
        if saved is None or url != saved.url:
            raise _token_required()
        try:
            token = paperless.decrypt_token(saved.token_encrypted)
        except paperless.PaperlessError as error:
            return PaperlessTestResult(ok=False, error=error.message)
    # No connection is held while Paperless takes its time to answer.
    session.commit()
    failure = paperless.test_connection(client, url, token)
    return PaperlessTestResult(ok=failure is None, error=failure)


@router.delete("/", response_model=PaperlessDisconnected)
def disconnect(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Disconnect Paperless (FR-04.8). Nothing in Paperless is deleted, and the
    attachments kept there stay as they are, out of reach until a connection
    is set again; the answer says how many. PDFs still waiting to be handed
    over stay in Taskly.
    """
    if paperless.get_connection(session, current_user.id) is None:
        raise HTTPException(
            status_code=NOT_CONNECTED_STATUS,
            detail={
                "code": paperless.NOT_CONNECTED_CODE,
                "message": "Paperless is not connected.",
            },
        )
    unreachable = paperless.disconnect(session, current_user.id)
    return PaperlessDisconnected(unreachable_documents=unreachable)
