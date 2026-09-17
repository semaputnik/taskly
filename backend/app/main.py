import re
from collections.abc import Awaitable, Callable
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

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

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
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


app.include_router(api_router, prefix=settings.API_V1_STR)
app.frontend("/", directory=FRONTEND_DIR)
