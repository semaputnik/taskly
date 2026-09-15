import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.api.deps import get_attachment_storage
from app.core.config import settings
from app.core.storage import AttachmentStorage
from app.main import app
from app.models import UserCreate
from tests.utils.utils import random_email, random_lower_string


class InMemoryAttachmentStorage(AttachmentStorage):
    """
    A storage double that never touches a real filesystem, so the test suite
    can assert on exactly what a delete released without disk I/O.
    """

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self.files[key] = data

    def get(self, key: str) -> bytes:
        try:
            return self.files[key]
        except KeyError:
            raise FileNotFoundError(key) from None

    def delete(self, key: str) -> None:
        self.files.pop(key, None)


@pytest.fixture(autouse=True)
def storage():
    fake_storage = InMemoryAttachmentStorage()
    app.dependency_overrides[get_attachment_storage] = lambda: fake_storage
    yield fake_storage
    del app.dependency_overrides[get_attachment_storage]


def _headers_for_new_user(client: TestClient, db: Session) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    crud.create_user(session=db, user_create=user_in)

    login_data = {"username": email, "password": password}
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_task(
    client: TestClient, headers: dict[str, str], title: str, **fields: object
) -> dict:
    r = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json={"title": title, **fields},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _upload(
    client: TestClient,
    headers: dict[str, str],
    task_id: str,
    filename: str = "notes.txt",
    content: bytes = b"hello world",
    content_type: str = "text/plain",
):
    return client.post(
        f"{settings.API_V1_STR}/tasks/{task_id}/attachments/",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


def _list_attachments(client: TestClient, headers: dict[str, str], task_id: str):
    return client.get(
        f"{settings.API_V1_STR}/tasks/{task_id}/attachments/", headers=headers
    )


def test_a_file_can_be_uploaded_to_a_task(
    client: TestClient, db: Session, storage: InMemoryAttachmentStorage
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Buy milk")

    r = _upload(client, headers, task["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "notes.txt"
    assert body["content_type"] == "text/plain"
    assert body["size"] == len(b"hello world")
    assert body["task_id"] == task["id"]
    assert storage.files[body["id"]] == b"hello world"

    listed = _list_attachments(client, headers, task["id"])
    assert listed.status_code == 200
    assert listed.json()["count"] == 1


def test_a_file_can_be_uploaded_to_a_subtask(client: TestClient, db: Session) -> None:
    headers = _headers_for_new_user(client, db)
    root = _create_task(client, headers, "Root")
    subtask = _create_task(client, headers, "Subtask", parent_id=root["id"])

    r = _upload(client, headers, subtask["id"])
    assert r.status_code == 200, r.text


def test_a_task_can_carry_multiple_attachments_of_any_type(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")

    _upload(client, headers, task["id"], filename="a.txt", content_type="text/plain")
    _upload(
        client,
        headers,
        task["id"],
        filename="b.bin",
        content_type="application/x-nonsense",
    )
    _upload(client, headers, task["id"], filename="c.png", content_type="image/png")

    r = _list_attachments(client, headers, task["id"])
    assert r.json()["count"] == 3


def test_downloading_returns_the_exact_bytes_uploaded(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    content = b"\x00\x01exact bytes\xffdone"

    uploaded = _upload(client, headers, task["id"], content=content).json()

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 200
    assert r.content == content
    # Starlette appends a charset to text media types on the wire; the stored
    # content type itself (asserted on upload) stays exactly what was sent.
    assert r.headers["content-type"].startswith("text/plain")
    assert "notes.txt" in r.headers["content-disposition"]


def test_downloading_a_non_latin1_filename_does_not_crash(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    uploaded = _upload(client, headers, task["id"], filename="файл.txt").json()
    assert uploaded["filename"] == "файл.txt"

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 200
    assert (
        "filename*=UTF-8''%D1%84%D0%B0%D0%B9%D0%BB.txt"
        in r.headers["content-disposition"]
    )


def test_a_filename_with_a_backslash_does_not_break_the_header(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    uploaded = _upload(client, headers, task["id"], filename="evil\\").json()

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 200
    # The fallback must stay a well-formed quoted-string: no bare backslash
    # left to escape whatever character follows it, including the closing
    # quote itself.
    disposition = r.headers["content-disposition"]
    fallback = disposition.split('filename="')[1].split('"')[0]
    assert "\\" not in fallback
    assert "filename*=UTF-8''evil%5C" in disposition


def test_a_filename_with_a_slash_is_percent_encoded(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    uploaded = _upload(client, headers, task["id"], filename="reports/q3.txt").json()

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 200
    # RFC 5987's attr-char grammar excludes "/", so it has to be percent
    # encoded like anything else outside the safe set, not passed through.
    assert "filename*=UTF-8''reports%2Fq3.txt" in r.headers["content-disposition"]


def test_downloading_a_non_ascii_content_type_does_not_crash(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    uploaded = _upload(
        client, headers, task["id"], content_type="text/plain; charset=кодировка"
    ).json()
    # Not asserting the exact bytes: the test client's own multipart encoder
    # is Latin-1 only and already mangles this on the way out. What matters
    # is that it stays a non-ASCII value, so it exercises the fallback below.
    assert not uploaded["content_type"].isascii()

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 200
    # The unsafe value is never put on the wire: the response header falls
    # back to something every client can parse.
    assert r.headers["content-type"] == "application/octet-stream"


def test_an_overlong_filename_and_content_type_are_truncated_not_rejected(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")

    r = _upload(
        client,
        headers,
        task["id"],
        filename="x" * 300 + ".txt",
        content_type="y" * 300,
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["filename"]) == 255
    assert len(r.json()["content_type"]) == 255


def test_downloading_an_attachment_whose_bytes_are_missing_is_a_404(
    client: TestClient, db: Session, storage: InMemoryAttachmentStorage
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    uploaded = _upload(client, headers, task["id"]).json()
    # Simulate the row existing with its bytes gone from storage, without
    # going through the delete endpoint (which removes the row too).
    storage.files.pop(uploaded["id"])

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 404


def test_deleting_an_attachment_releases_its_storage_bytes(
    client: TestClient, db: Session, storage: InMemoryAttachmentStorage
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    uploaded = _upload(client, headers, task["id"]).json()
    assert uploaded["id"] in storage.files

    r = client.delete(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 200, r.text
    assert uploaded["id"] not in storage.files

    listed = _list_attachments(client, headers, task["id"])
    assert listed.json()["count"] == 0


def test_a_user_cannot_read_attachments_on_another_users_task(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")
    _upload(client, headers_a, task["id"])

    r = _list_attachments(client, headers_b, task["id"])
    assert r.status_code == 404


def test_a_user_cannot_upload_to_another_users_task(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")

    r = _upload(client, headers_b, task["id"])
    assert r.status_code == 404


def test_a_user_cannot_download_another_users_attachment(
    client: TestClient, db: Session
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")
    uploaded = _upload(client, headers_a, task["id"]).json()

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers_b
    )
    assert r.status_code == 404


def test_a_user_cannot_delete_another_users_attachment(
    client: TestClient, db: Session, storage: InMemoryAttachmentStorage
) -> None:
    headers_a = _headers_for_new_user(client, db)
    headers_b = _headers_for_new_user(client, db)
    task = _create_task(client, headers_a, "A's task")
    uploaded = _upload(client, headers_a, task["id"]).json()

    r = client.delete(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers_b
    )
    assert r.status_code == 404
    assert uploaded["id"] in storage.files


def test_uploading_a_file_over_the_size_limit_is_rejected(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ATTACHMENT_MAX_SIZE_BYTES", 10)
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")

    r = _upload(client, headers, task["id"], content=b"this is more than ten bytes")
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "attachment_too_large"
    assert r.json()["detail"]["limit"] == 10

    assert _list_attachments(client, headers, task["id"]).json()["count"] == 0


def test_uploading_on_an_unknown_task_is_rejected(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)

    r = _upload(client, headers, "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_attachments_survive_a_deleted_task(
    client: TestClient, db: Session, storage: InMemoryAttachmentStorage
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Doomed")
    uploaded = _upload(client, headers, task["id"]).json()

    r = client.delete(f"{settings.API_V1_STR}/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200

    # The task is only soft-deleted and no longer reachable; its attachment's
    # bytes must stay behind so a restore brings the file back too.
    assert _list_attachments(client, headers, task["id"]).status_code == 404
    assert uploaded["id"] in storage.files


def test_an_attachment_on_a_deleted_task_cannot_be_downloaded_or_deleted(
    client: TestClient, db: Session
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Doomed")
    uploaded = _upload(client, headers, task["id"]).json()

    client.delete(f"{settings.API_V1_STR}/tasks/{task['id']}", headers=headers)

    r = client.get(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 404

    r = client.delete(
        f"{settings.API_V1_STR}/attachments/{uploaded['id']}", headers=headers
    )
    assert r.status_code == 404


def test_deleting_your_own_account_releases_attachment_storage_bytes(
    client: TestClient, db: Session, storage: InMemoryAttachmentStorage
) -> None:
    headers = _headers_for_new_user(client, db)
    task = _create_task(client, headers, "Task")
    uploaded = _upload(client, headers, task["id"]).json()
    assert uploaded["id"] in storage.files

    # Deleting the account cascades the attachment row away at the database
    # level; its bytes must not be left behind with nothing pointing at them.
    r = client.delete(f"{settings.API_V1_STR}/users/me", headers=headers)
    assert r.status_code == 200
    assert uploaded["id"] not in storage.files
