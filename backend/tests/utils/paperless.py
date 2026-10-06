"""
A stub Paperless-ngx for tests: the few endpoints Taskly calls, behind an
`httpx` mock transport, with the state a real one would keep (documents, tags,
notes, consumption tasks). Nothing here reaches a network.

It records every request, so a test can say what Taskly asked for and, above
all, that it never sent a DELETE.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

TOKEN = "stub-token"
BASE_URL = "https://paperless.example.com"


@dataclass
class Document:
    id: int
    title: str
    checksum: str
    original: bytes
    tags: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ConsumptionTask:
    task_id: str
    status: str
    document_id: int | None = None
    result: str | None = None
    polls_left: int = 0
    data: bytes = b""
    title: str = ""
    tags: list[int] = field(default_factory=list)


def parse_multipart(
    request: httpx.Request,
) -> tuple[dict[str, list[str]], dict[str, tuple[str, bytes]]]:
    """The form fields and files of a multipart request."""
    content_type = request.headers["content-type"]
    boundary = content_type.split("boundary=")[1].encode()
    fields: dict[str, list[str]] = {}
    files: dict[str, tuple[str, bytes]] = {}
    for part in request.content.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        head, _, body = part.partition(b"\r\n\r\n")
        text = head.decode()
        name = re.search(r'name="([^"]*)"', text)
        assert name is not None
        filename = re.search(r'filename="([^"]*)"', text)
        if filename:
            files[name.group(1)] = (filename.group(1), body)
        else:
            fields.setdefault(name.group(1), []).append(body.decode())
    return fields, files


class StubPaperless:
    """
    A Paperless-ngx that answers as the real one does for what Taskly asks.

    `consume` says what happens to a posted file: `success` (consumed once
    `polls_to_consume` polls have passed), `pending` (never finishes) or
    `failure`. `down` makes every request fail to connect; `status` answers
    every request with that status instead.
    """

    def __init__(self) -> None:
        self.documents: dict[int, Document] = {}
        self.tags: dict[int, str] = {}
        self.tasks: dict[str, ConsumptionTask] = {}
        self.requests: list[httpx.Request] = []
        self.token = TOKEN
        self.consume = "success"
        self.polls_to_consume = 0
        self.failure_result = "file.pdf: Not consuming file.pdf: broken"
        self.down = False
        self.status: int | None = None
        self.hold_document_id: bool = True
        self._next_id = 100

    # --- Setting the stage ---------------------------------------------------

    def has_document(self, data: bytes, title: str = "existing") -> Document:
        """A document Paperless already holds, as if filed there by hand."""
        document = Document(
            id=self._take_id(),
            title=title,
            checksum=hashlib.md5(data).hexdigest(),
            original=data,
        )
        self.documents[document.id] = document
        return document

    def has_tag(self, name: str) -> int:
        tag_id = self._take_id()
        self.tags[tag_id] = name
        return tag_id

    def _take_id(self) -> int:
        self._next_id += 1
        return self._next_id

    # --- What was asked ------------------------------------------------------

    def calls(self, method: str, path: str | None = None) -> list[httpx.Request]:
        return [
            r
            for r in self.requests
            if r.method == method and (path is None or r.url.path == path)
        ]

    @property
    def deletes(self) -> list[httpx.Request]:
        return self.calls("DELETE")

    @property
    def posted(self) -> list[httpx.Request]:
        return self.calls("POST", "/api/documents/post_document/")

    # --- The transport -------------------------------------------------------

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        if self.status is not None:
            return httpx.Response(self.status, json={"detail": "stubbed"})
        if request.headers.get("authorization") != f"Token {self.token}":
            return httpx.Response(
                401, json={"detail": "Invalid token."}, request=request
            )
        path = request.url.path
        params = request.url.params
        method = request.method
        if path == "/api/documents/" and method == "GET":
            return self._documents(params)
        if path == "/api/documents/post_document/" and method == "POST":
            return self._post_document(request)
        if path == "/api/tags/" and method == "GET":
            name = params.get("name__iexact", "").lower()
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": i, "name": n}
                        for i, n in self.tags.items()
                        if not name or n.lower() == name
                    ]
                },
            )
        if path == "/api/tags/" and method == "POST":
            name = json.loads(request.content)["name"]
            if name.lower() in {n.lower() for n in self.tags.values()}:
                return httpx.Response(400, json={"name": ["Name must be unique."]})
            tag_id = self._take_id()
            self.tags[tag_id] = name
            return httpx.Response(201, json={"id": tag_id, "name": name})
        if path == "/api/tasks/" and method == "GET":
            return self._task(params.get("task_id", ""))
        match = re.fullmatch(r"/api/documents/(\d+)/(.*)", path)
        if match:
            return self._document(request, int(match.group(1)), match.group(2))
        return httpx.Response(404, json={"detail": "Not found."})

    def _documents(self, params: httpx.QueryParams) -> httpx.Response:
        checksum = params.get("checksum__iexact")
        found = [
            d
            for d in self.documents.values()
            if checksum is None or d.checksum.lower() == checksum.lower()
        ]
        return httpx.Response(
            200, json={"count": len(found), "results": [{"id": d.id} for d in found]}
        )

    def _post_document(self, request: httpx.Request) -> httpx.Response:
        fields, files = parse_multipart(request)
        _filename, data = files["document"]
        task = ConsumptionTask(
            task_id=str(uuid.uuid4()),
            status="PENDING",
            polls_left=self.polls_to_consume,
            data=data,
            title=fields.get("title", [""])[0],
            tags=[int(t) for t in fields.get("tags", [])],
        )
        self.tasks[task.task_id] = task
        return httpx.Response(200, json=task.task_id)

    def _task(self, task_id: str) -> httpx.Response:
        task = self.tasks.get(task_id)
        if task is None:
            return httpx.Response(200, json=[])
        if task.status == "PENDING":
            if self.consume == "pending":
                pass
            elif task.polls_left > 0:
                task.polls_left -= 1
            elif self.consume == "failure":
                task.status, task.result = "FAILURE", self.failure_result
            else:
                self._consume(task)
        body: dict[str, Any] = {
            "task_id": task.task_id,
            "status": task.status,
            "result": task.result,
            "related_document": (
                str(task.document_id)
                if task.document_id is not None and self.hold_document_id
                else None
            ),
        }
        return httpx.Response(200, json=[body])

    def _consume(self, task: ConsumptionTask) -> None:
        checksum = hashlib.md5(task.data).hexdigest()
        existing = next(
            (d for d in self.documents.values() if d.checksum == checksum), None
        )
        if existing is not None:
            # What Paperless does with a file it already holds.
            task.status = "FAILURE"
            task.result = (
                f"{task.title}: Not consuming: It is a duplicate of {existing.title}"
            )
            return
        document = Document(
            id=self._take_id(),
            title=task.title,
            checksum=checksum,
            original=task.data,
            tags=list(task.tags),
        )
        self.documents[document.id] = document
        task.status, task.document_id = "SUCCESS", document.id
        task.result = f"Success. New document id {document.id} created"

    def _document(
        self, request: httpx.Request, document_id: int, rest: str
    ) -> httpx.Response:
        document = self.documents.get(document_id)
        if document is None:
            return httpx.Response(
                404, json={"detail": "No Document matches the query."}
            )
        method = request.method
        if rest == "" and method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": document.id,
                    "title": document.title,
                    "tags": document.tags,
                },
            )
        if rest == "" and method == "PATCH":
            document.tags = list(json.loads(request.content)["tags"])
            return httpx.Response(200, json={"id": document.id, "tags": document.tags})
        if rest == "notes/" and method == "GET":
            return httpx.Response(
                200, json=[{"id": i, "note": n} for i, n in enumerate(document.notes)]
            )
        if rest == "notes/" and method == "POST":
            document.notes.append(json.loads(request.content)["note"])
            return httpx.Response(
                200, json=[{"id": i, "note": n} for i, n in enumerate(document.notes)]
            )
        if rest == "download/" and method == "GET":
            original = request.url.params.get("original") == "true"
            return httpx.Response(
                200,
                content=document.original if original else b"%PDF-ARCHIVED-COPY",
                headers={"content-type": "application/pdf"},
            )
        return httpx.Response(405, json={"detail": "Method not allowed."})


PDF = b"%PDF-1.4\n%stub document\n"


def pdf(label: str = "one") -> bytes:
    """A PDF by its content; each label is a different file."""
    return PDF + label.encode()
