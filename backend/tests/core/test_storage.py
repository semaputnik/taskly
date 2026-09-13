from pathlib import Path

import pytest

from app.core.storage import LocalAttachmentStorage


def test_put_then_get_round_trips_the_exact_bytes(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path / "attachments")

    storage.put("some-key", b"exact bytes")

    assert storage.get("some-key") == b"exact bytes"


def test_the_storage_root_is_created_on_demand(tmp_path: Path) -> None:
    root = tmp_path / "does" / "not" / "exist" / "yet"

    LocalAttachmentStorage(root)

    assert root.is_dir()


def test_delete_removes_the_file(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path)
    storage.put("some-key", b"data")

    storage.delete("some-key")

    with pytest.raises(FileNotFoundError):
        storage.get("some-key")


def test_deleting_a_missing_key_is_not_an_error(tmp_path: Path) -> None:
    storage = LocalAttachmentStorage(tmp_path)

    storage.delete("never-existed")
