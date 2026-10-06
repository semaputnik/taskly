import asyncio
import contextlib
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app import passkeys, webhooks
from app.api.main import api_router
from app.core.config import settings

FRONTEND_DIR = Path(__file__).parent / "frontend"

# What Vite names a built file: `name-<8-character hash>.ext`. The hash changes
# whenever the content does, so such a file can be kept forever.
HASHED_ASSET = re.compile(r"^/assets/[^/]+-[A-Za-z0-9_-]{8}\.[a-z0-9]+$")


def frontend_cache_control(path: str) -> str | None:
    """
    How long a browser may keep a frontend file, or None for API responses,
    which set their own.

    A hashed build file never changes under its name, so it is kept for a year
    and never revalidated. Everything else — `index.html` above all, which
    names the current hashes — is revalidated on every load, so a deploy
    reaches the reader on their next visit rather than a cache lifetime later.
    """
    if path.startswith(settings.API_V1_STR):
        return None
    if HASHED_ASSET.match(path):
        return "public, max-age=31536000, immutable"
    return "no-cache"


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """
    Run the webhook delivery loop for as long as this process serves requests
    (ADR-0009). There is no separate worker: every API process drains the
    outbox, and the table is the only state, so a restart loses nothing.
    """
    loop = None
    if settings.WEBHOOK_DELIVERY_LOOP:
        loop = asyncio.create_task(webhooks.drain_forever())
    try:
        yield
    finally:
        if loop is not None:
            loop.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await loop


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "bots",
            "description": webhooks.DELIVERY_CONTRACT,
        },
        {
            "name": "paperless",
            "description": (
                "The owner's Paperless-ngx connection (FR-04.4). While one is "
                "set, every PDF attached to their tasks is kept in Paperless: "
                "attachments report `kept_in` (`taskly` or `paperless`), the "
                "document link, and, while a PDF is on its way or its "
                "hand-over failed, `paperless_handover` with the reason. A "
                "failed hand-over is sent again with "
                "`POST /attachments/{id}/resend`. The token is never returned."
            ),
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The frontend's JavaScript and the API's JSON both shrink to a fraction when
# compressed, and a phone on a slow connection pays for every byte. Neither
# deployment puts a compressing proxy in front of the app, so the app does it.
# Bodies carry no cookie-borne secret, so compression gives BREACH nothing to
# work with: requests authenticate with a bearer header a third-party page
# cannot send.
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def cache_frontend_files(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    cache_control = frontend_cache_control(request.url.path)
    if cache_control and response.status_code == 200:
        response.headers["Cache-Control"] = cache_control
    return response


@app.exception_handler(passkeys.PasskeyError)
async def passkey_refused(_request: Request, error: Exception) -> Response:
    """
    A ceremony or account change the caller is refused (F-12), in words safe
    to show: 404 for something that is not there, 400 for everything else.
    """
    not_found = isinstance(error, passkeys.PasskeyNotFound | passkeys.UserNotFound)
    return JSONResponse(
        status_code=404 if not_found else 400, content={"detail": str(error)}
    )


app.include_router(api_router, prefix=settings.API_V1_STR)
app.frontend("/", directory=FRONTEND_DIR)
