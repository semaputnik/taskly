from abc import ABC, abstractmethod
from pathlib import Path


class AttachmentStorage(ABC):
    """
    Where an attachment's bytes live, kept to put/get/delete on purpose
    (ADR-0002): a richer interface would be harder for a future remote
    backend, such as a per-user Paperless-ngx instance, to satisfy. Nothing
    above this interface may assume the bytes sit on a local filesystem.
    """

    @abstractmethod
    def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Raise `FileNotFoundError` if `key` names no stored bytes."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalAttachmentStorage(AttachmentStorage):
    """The default backend (ADR-0002): files sit on the local filesystem."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._root / key

    def put(self, key: str, data: bytes) -> None:
        self._path(key).write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
