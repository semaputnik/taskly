"""A storage double for attachments, installed by the `storage` fixture in conftest."""

from app.core.storage import AttachmentStorage


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
